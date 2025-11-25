#!/usr/bin/env python3
"""
EVCC Battery Charging Controller

This script implements intelligent battery charging from the grid based on:
- Battery state of charge (SoC)
- Current grid charge limit setting
- Solar forecast for next day
- Dynamic electricity pricing

Author: Automated Battery Management
"""

import json
import logging
from logging.handlers import TimedRotatingFileHandler
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import requests
from configparser import ConfigParser


class EVCCBatteryController:
    """Controller for EVCC battery charging based on price optimization."""
    
    def __init__(self, config_file: str = "battery_config.ini"):
        """Initialize the controller with configuration."""
        self.config = self._load_config(config_file)
        self.base_url = f"http://{self.config['evcc']['host']}:{self.config['evcc']['port']}/api"
        self.session = requests.Session()
        
        # Setup logging with rotation (retain only last N days)
        log_file = os.path.expanduser(self.config['logging']['file'])
        retention_days = int(self.config['logging'].get('retention_days', '3'))
        # TimedRotatingFileHandler keeps 'backupCount' old files in addition to the current.
        # To retain ONLY the last <retention_days> days including today, we set backupCount = retention_days - 1.
        backup_count = max(retention_days - 1, 0)

        # Create parent directory if missing
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        logger = logging.getLogger(__name__)
        # Avoid duplicate handlers if instantiated multiple times (e.g., in tests)
        if logger.handlers:
            for h in list(logger.handlers):
                logger.removeHandler(h)

        logger.setLevel(getattr(logging, self.config['logging']['level'].upper()))

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        rotating_handler = TimedRotatingFileHandler(
            log_file,
            when='midnight',
            interval=1,
            backupCount=backup_count,
            utc=True,
            encoding='utf-8'
        )
        rotating_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        logger.addHandler(rotating_handler)
        logger.addHandler(console_handler)
        logger.propagate = False

        self.logger = logger
        
    def _load_config(self, config_file: str) -> ConfigParser:
        """Load configuration from INI file."""
        config = ConfigParser()
        
        # Default configuration
        default_config = {
            'evcc': {
                'host': '192.168.0.2',
                'port': '7070',
                'password': ''
            },
            'thresholds': {
                'battery_low_soc': '30',
                'battery_high_soc': '85',
                'min_solar_forecast': '10',
                'solar_forecast_hours': '24',
                'min_price_spread': '10'
            },
            'logging': {
                'level': 'INFO',
                'file': '/var/log/evcc_battery_controller.log',
                'retention_days': '3'  # Keep only the last 3 days (current + previous 2)
            }
        }
        
        # Create default config file if it doesn't exist
        if not os.path.exists(config_file):
            config.read_dict(default_config)
            with open(config_file, 'w') as f:
                config.write(f)
            print(f"Created default configuration file: {config_file}")
            print("Please review and update the configuration before running again.")
            sys.exit(0)
        
        config.read(config_file)
        return config
    
    def _authenticate(self) -> bool:
        """Authenticate with EVCC if password is configured."""
        password = self.config['evcc']['password']
        if not password:
            return True
            
        try:
            response = self.session.post(
                f"{self.base_url}/auth/login",
                json={"password": password},
                timeout=10
            )
            if response.status_code == 200:
                self.logger.info("Authentication successful")
                return True
            else:
                self.logger.error(f"Authentication failed: {response.status_code}")
                return False
        except requests.RequestException as e:
            self.logger.error(f"Authentication error: {e}")
            return False
    
    def _get_state(self) -> Dict:
        """Get the current EVCC system state."""
        try:
            response = self.session.get(f"{self.base_url}/state", timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Handle different response formats
            if 'result' in data:
                return data['result']
            else:
                # If no 'result' wrapper, return the data directly
                return data
        except requests.RequestException as e:
            self.logger.error(f"Failed to get system state: {e}")
            raise
    
    def _get_tariff_data(self, tariff_type: str = "grid") -> List[Dict]:
        """Get tariff data for price analysis."""
        try:
            response = self.session.get(f"{self.base_url}/tariff/{tariff_type}", timeout=10)
            if response.status_code == 404:
                self.logger.warning(f"Tariff type '{tariff_type}' not configured")
                return []
            response.raise_for_status()
            data = response.json()
            
            # Handle different response formats
            if 'result' in data and 'rates' in data['result']:
                return data['result']['rates']
            elif 'rates' in data:
                return data['rates']
            else:
                self.logger.warning(f"Unexpected tariff response format: {data}")
                return []
        except requests.RequestException as e:
            self.logger.error(f"Failed to get tariff data: {e}")
            return []
    
    def _get_solar_forecast(self) -> float:
        """Get solar forecast for the configured time window."""
        try:
            # Get forecast window from config (0 = disabled)
            forecast_hours = float(self.config['thresholds']['solar_forecast_hours'])
            if forecast_hours <= 0:
                self.logger.debug("Solar forecast disabled (solar_forecast_hours = 0)")
                return 0.0
            
            response = self.session.get(f"{self.base_url}/tariff/solar", timeout=10)
            if response.status_code == 404:
                self.logger.warning("Solar forecast not configured")
                return 0.0
            response.raise_for_status()
            
            data = response.json()
            
            # Handle different response formats
            if 'result' in data and 'rates' in data['result']:
                solar_data = data['result']['rates']
            elif 'rates' in data:
                solar_data = data['rates']
            else:
                self.logger.warning("No solar rates found in response")
                return 0.0
            
            from datetime import timezone
            now = datetime.now(timezone.utc)
            end_forecast_window = now + timedelta(hours=forecast_hours)
            
            forecast_total = 0.0
            for rate in solar_data:
                rate_time_str = rate['start'].replace('Z', '+00:00')
                rate_time = datetime.fromisoformat(rate_time_str)
                
                # Ensure rate_time is timezone-aware
                if rate_time.tzinfo is None:
                    rate_time = rate_time.replace(tzinfo=timezone.utc)
                    
                # Only count solar production for the configured window
                if now <= rate_time <= end_forecast_window:
                    # Convert from W to kWh (assuming hourly intervals)
                    forecast_total += rate['value'] / 1000
            
            self.logger.debug(f"Solar forecast for next {forecast_hours:.0f} hours: {forecast_total:.1f} kWh")
            return forecast_total
        except requests.RequestException as e:
            self.logger.warning(f"Could not get solar forecast: {e}")
            return 0.0
    
    def _get_current_battery_charge_limit(self) -> float:
        """Get current battery grid charge limit (in cents/kWh)."""
        try:
            state = self._get_state()
            # Check if battery grid charge limit is set
            if 'batteryGridChargeLimit' in state and state['batteryGridChargeLimit'] is not None:
                return state['batteryGridChargeLimit']
            return 0.0
        except Exception as e:
            self.logger.error(f"Failed to get battery charge limit: {e}")
            return 0.0
    
    def _set_battery_charge_limit(self, cost_limit: float) -> bool:
        """Set battery grid charge limit."""
        try:
            if cost_limit <= 0:
                # Remove limit
                response = self.session.delete(f"{self.base_url}/batterygridchargelimit", timeout=10)
                self.logger.info("Removed battery grid charge limit")
            else:
                # Set limit (cost_limit is in EUR/kWh as expected by API)
                response = self.session.post(
                    f"{self.base_url}/batterygridchargelimit/{cost_limit}",
                    timeout=10
                )
                self.logger.info(f"Set battery grid charge limit to {cost_limit:.4f} EUR/kWh")
            
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            self.logger.error(f"Failed to set battery charge limit: {e}")
            return False
    
    def _analyze_prices(self) -> Tuple[float, float, float, float]:
        """Analyze current and upcoming prices to find min/max spread and current price.
        
        Returns:
            Tuple of (current_price, min_price, max_price, price_spread)
        """
        tariff_data = self._get_tariff_data("grid")
        if not tariff_data:
            self.logger.warning("No price data available")
            return 0.0, 0.0, 0.0, 0.0
        
        # Get configurable hours of price data
        from datetime import timezone
        price_window_hours = float(self.config['thresholds']['price_analysis_hours'])
        now = datetime.now(timezone.utc)
        analysis_end = now + timedelta(hours=price_window_hours)
        
        current_price = None
        relevant_prices = []
        
        for rate in tariff_data:
            rate_time_str = rate['start'].replace('Z', '+00:00')
            rate_time = datetime.fromisoformat(rate_time_str)
            
            # Ensure rate_time is timezone-aware
            if rate_time.tzinfo is None:
                rate_time = rate_time.replace(tzinfo=timezone.utc)
            
            # Find current price (the most recent rate that has started)
            if rate_time <= now and current_price is None:
                current_price = rate['value']
            
            if now <= rate_time <= analysis_end:
                relevant_prices.append(rate['value'])
        
        # If current price not found in past rates, use first future rate
        if current_price is None and relevant_prices:
            current_price = relevant_prices[0]
        
        if not relevant_prices or current_price is None:
            self.logger.warning(f"No price data for next {price_window_hours} hours")
            return 0.0, 0.0, 0.0, 0.0
        
        min_price = min(relevant_prices)
        max_price = max(relevant_prices)
        price_spread = (max_price - min_price) * 100  # Convert to cents/kWh
        
        self.logger.debug(f"Price analysis ({price_window_hours}h window): Current={current_price:.4f}, Min={min_price:.4f}, Max={max_price:.4f}, Spread={price_spread:.2f} cents/kWh")
        return current_price, min_price, max_price, price_spread
    
    def _get_battery_soc(self) -> float:
        """Get current battery state of charge."""
        try:
            state = self._get_state()
            
            # Look for battery SoC in various possible locations
            battery_soc = None
            if 'batterySoc' in state:
                battery_soc = state['batterySoc']
            elif 'site' in state and 'batterySoc' in state['site']:
                battery_soc = state['site']['batterySoc']
            elif 'battery' in state and 'soc' in state['battery']:
                battery_soc = state['battery']['soc']
            
            if battery_soc is not None:
                self.logger.debug(f"Current battery SoC: {battery_soc}%")
                return battery_soc
            else:
                self.logger.warning("Could not determine battery SoC from state")
                return 0.0
                
        except Exception as e:
            self.logger.error(f"Failed to get battery SoC: {e}")
            return 0.0
    
    def run_control_logic(self) -> None:
        """Execute the main battery charging control logic."""
        self.logger.debug("=== Starting Battery Charging Control Logic ===")
        
        # Authenticate if needed
        if not self._authenticate():
            return
        
        try:
            # Get current system state
            battery_soc = self._get_battery_soc()
            current_charge_limit = self._get_current_battery_charge_limit()
            solar_forecast = self._get_solar_forecast()
            current_price, min_price, max_price, price_spread = self._analyze_prices()
            
            # Load thresholds from config
            low_soc_threshold = float(self.config['thresholds']['battery_low_soc'])
            high_soc_threshold = float(self.config['thresholds']['battery_high_soc'])
            min_solar_threshold = float(self.config['thresholds']['min_solar_forecast'])
            solar_forecast_hours = float(self.config['thresholds']['solar_forecast_hours'])
            min_price_spread_threshold = float(self.config['thresholds']['min_price_spread'])
            
            self.logger.debug(f"Current state: SoC={battery_soc}%, "
                           f"Charge limit={current_charge_limit:.4f} EUR/kWh, "
                           f"Solar forecast ({solar_forecast_hours:.0f}h)={solar_forecast:.1f} kWh, "
                           f"Current price={current_price:.4f} EUR/kWh, "
                           f"Price spread={price_spread:.2f} cents/kWh")
            
            # Rule 1: Enable charging when conditions are met
            # Check solar condition only if solar forecast is enabled
            solar_condition_met = (solar_forecast_hours <= 0) or (solar_forecast < min_solar_threshold)
            
            # Only charge when current price is LOWER than maximum in forecast window
            # This catches the typical winter scenario: low early morning prices before everyone wakes up
            current_price_cents = current_price * 100
            max_price_cents = max_price * 100
            is_price_advantageous = current_price < max_price  # Current price must be lower than future max
            
            if (battery_soc < low_soc_threshold and 
                solar_condition_met and
                price_spread > min_price_spread_threshold and
                is_price_advantageous):  # Only charge when current price is lower than upcoming prices
                
                # Log conditions when they are met (INFO level)
                if solar_forecast_hours <= 0:
                    solar_msg = "Solar forecast disabled"
                else:
                    solar_msg = f"Solar={solar_forecast:.1f} < {min_solar_threshold} kWh"
                
                self.logger.info(f"Charging conditions met: SoC={battery_soc}% < {low_soc_threshold}%, "
                               f"{solar_msg}, "
                               f"Price spread={price_spread:.2f} > {min_price_spread_threshold} cents, "
                               f"Current price={current_price_cents:.1f} cents < Max price={max_price_cents:.1f} cents")
                
                charge_limit = math.ceil(min_price * 100) / 100  # Round up to next cent, then back to EUR
                self.logger.info(f"Setting battery grid charge limit to {charge_limit:.4f} EUR/kWh")
                self._set_battery_charge_limit(charge_limit)
            
            # Log why we're NOT charging if conditions are close but not met
            elif battery_soc < low_soc_threshold and solar_condition_met and price_spread > min_price_spread_threshold:
                if not is_price_advantageous:
                    self.logger.info(f"NOT charging: Current price {current_price_cents:.1f} cents is NOT lower than max price {max_price_cents:.1f} cents. "
                                   f"Waiting for prices to rise before charging.")
            
            # Rule 2: Disable charging when battery is sufficiently charged
            if (battery_soc > high_soc_threshold and current_charge_limit > 0):
                self.logger.info(f"Disabling charging: SoC={battery_soc}% > {high_soc_threshold}%, "
                               f"Current limit={current_charge_limit:.4f} EUR/kWh")
                self.logger.info("Battery sufficiently charged. Disabling grid charging.")
                self._set_battery_charge_limit(0)
            
            else:
                self.logger.debug("No action required based on current conditions")
                
        except Exception as e:
            self.logger.error(f"Error in control logic: {e}")
        
        self.logger.debug("=== Battery Charging Control Logic Complete ===")


def main():
    """Main entry point."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(script_dir, "battery_config.ini")
    
    controller = EVCCBatteryController(config_file)
    controller.run_control_logic()


if __name__ == "__main__":
    main()
