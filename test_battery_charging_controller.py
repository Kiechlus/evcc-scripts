#!/usr/bin/env python3
"""
Unit tests for EVCC Battery Charging Controller

This module contains comprehensive unit tests for the battery charging controller,
mocking all external API calls and testing various scenarios.

Test Coverage:
- 27 total test methods covering all aspects of the controller
- Configuration: 7 tests (config loading, authentication)
- API Calls: 10 tests (state, tariff, solar forecast APIs)
- Logic Tests: 6 tests (charging decisions, conditions)
- Price Analysis: 4 tests (price calculation, spreads)
- Battery Control: 5 tests (SoC, charge limits)
- Edge Cases: 2 tests (timezone, empty data)
- Integration: 1 test (realistic end-to-end scenario)

Run with: python3 test_battery_charging_controller.py
"""

import json
import math
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch
from configparser import ConfigParser

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from battery_charging_controller import EVCCBatteryController


class TestEVCCBatteryController(unittest.TestCase):
    """Test cases for EVCCBatteryController."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a temporary config file for testing
        self.temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False)
        test_config = """
[evcc]
host = 192.168.0.2
port = 7070
password = 

[thresholds]
battery_low_soc = 30
battery_high_soc = 85
min_solar_forecast = 10
solar_forecast_hours = 24
price_analysis_hours = 12
min_price_spread = 10

[logging]
level = INFO
file = /tmp/test_evcc_battery_controller.log
"""
        self.temp_config.write(test_config)
        self.temp_config.close()
        
        # Create controller instance with test config
        self.controller = EVCCBatteryController(self.temp_config.name)
        
        # Mock the session to avoid real HTTP calls
        self.controller.session = Mock()

    def tearDown(self):
        """Clean up after each test method."""
        os.unlink(self.temp_config.name)

    def test_config_loading(self):
        """Test configuration loading."""
        self.assertEqual(self.controller.config['evcc']['host'], '192.168.0.2')
        self.assertEqual(self.controller.config['evcc']['port'], '7070')
        self.assertEqual(float(self.controller.config['thresholds']['battery_low_soc']), 30)
        self.assertEqual(float(self.controller.config['thresholds']['solar_forecast_hours']), 24)
        self.assertEqual(float(self.controller.config['thresholds']['price_analysis_hours']), 12)

    def test_authentication_no_password(self):
        """Test authentication when no password is configured."""
        self.controller.config['evcc']['password'] = ''
        result = self.controller._authenticate()
        self.assertTrue(result)

    def test_authentication_success(self):
        """Test successful authentication with password."""
        self.controller.config['evcc']['password'] = 'testpass'
        mock_response = Mock()
        mock_response.status_code = 200
        self.controller.session.post.return_value = mock_response
        
        result = self.controller._authenticate()
        self.assertTrue(result)
        self.controller.session.post.assert_called_once()

    def test_authentication_failure(self):
        """Test failed authentication."""
        self.controller.config['evcc']['password'] = 'testpass'
        mock_response = Mock()
        mock_response.status_code = 401
        self.controller.session.post.return_value = mock_response
        
        result = self.controller._authenticate()
        self.assertFalse(result)

    def test_get_state_with_result_wrapper(self):
        """Test getting system state with 'result' wrapper."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'result': {
                'batterySoc': 75,
                'batteryGridChargeLimit': 0.2
            }
        }
        mock_response.raise_for_status.return_value = None
        self.controller.session.get.return_value = mock_response
        
        state = self.controller._get_state()
        self.assertEqual(state['batterySoc'], 75)
        self.assertEqual(state['batteryGridChargeLimit'], 0.2)

    def test_get_state_without_result_wrapper(self):
        """Test getting system state without 'result' wrapper."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'batterySoc': 75,
            'batteryGridChargeLimit': 0.2
        }
        mock_response.raise_for_status.return_value = None
        self.controller.session.get.return_value = mock_response
        
        state = self.controller._get_state()
        self.assertEqual(state['batterySoc'], 75)

    def test_get_battery_soc_from_state(self):
        """Test getting battery SoC from various state formats."""
        test_cases = [
            ({'batterySoc': 45}, 45),
            ({'site': {'batterySoc': 67}}, 67),
            ({'battery': {'soc': 89}}, 89),
            ({'other': 'data'}, 0.0)  # No SoC found
        ]
        
        for state_data, expected_soc in test_cases:
            with patch.object(self.controller, '_get_state', return_value=state_data):
                soc = self.controller._get_battery_soc()
                self.assertEqual(soc, expected_soc)

    def test_get_current_battery_charge_limit(self):
        """Test getting current battery charge limit."""
        test_cases = [
            ({'batteryGridChargeLimit': 0.25}, 0.25),
            ({'batteryGridChargeLimit': None}, 0.0),
            ({'other': 'data'}, 0.0)  # No limit found
        ]
        
        for state_data, expected_limit in test_cases:
            with patch.object(self.controller, '_get_state', return_value=state_data):
                limit = self.controller._get_current_battery_charge_limit()
                self.assertEqual(limit, expected_limit)

    def test_get_tariff_data_with_result_wrapper(self):
        """Test getting tariff data with 'result' wrapper."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'result': {
                'rates': [
                    {'start': '2025-09-08T10:00:00Z', 'value': 0.15},
                    {'start': '2025-09-08T11:00:00Z', 'value': 0.20}
                ]
            }
        }
        mock_response.raise_for_status.return_value = None
        self.controller.session.get.return_value = mock_response
        
        rates = self.controller._get_tariff_data('grid')
        self.assertEqual(len(rates), 2)
        self.assertEqual(rates[0]['value'], 0.15)

    def test_get_tariff_data_not_configured(self):
        """Test getting tariff data when not configured (404)."""
        mock_response = Mock()
        mock_response.status_code = 404
        self.controller.session.get.return_value = mock_response
        
        rates = self.controller._get_tariff_data('grid')
        self.assertEqual(rates, [])

    def test_analyze_prices(self):
        """Test price analysis with mock data."""
        now = datetime.now(timezone.utc)
        mock_rates = [
            {'start': (now + timedelta(hours=1)).isoformat().replace('+00:00', 'Z'), 'value': 0.15},
            {'start': (now + timedelta(hours=2)).isoformat().replace('+00:00', 'Z'), 'value': 0.30},
            {'start': (now + timedelta(hours=3)).isoformat().replace('+00:00', 'Z'), 'value': 0.10},
        ]
        
        with patch.object(self.controller, '_get_tariff_data', return_value=mock_rates):
            min_price, max_price, price_spread = self.controller._analyze_prices()
            
            self.assertEqual(min_price, 0.10)
            self.assertEqual(max_price, 0.30)
            self.assertEqual(price_spread, 20.0)  # (0.30 - 0.10) * 100

    def test_analyze_prices_no_data(self):
        """Test price analysis with no data."""
        with patch.object(self.controller, '_get_tariff_data', return_value=[]):
            min_price, max_price, price_spread = self.controller._analyze_prices()
            
            self.assertEqual(min_price, 0.0)
            self.assertEqual(max_price, 0.0)
            self.assertEqual(price_spread, 0.0)

    def test_analyze_prices_configurable_window(self):
        """Test price analysis with configurable time window."""
        # Set price analysis window to 6 hours
        self.controller.config['thresholds']['price_analysis_hours'] = '6'
        
        now = datetime.now(timezone.utc)
        mock_rates = [
            {'start': (now + timedelta(hours=1)).isoformat().replace('+00:00', 'Z'), 'value': 0.15},  # Within 6h
            {'start': (now + timedelta(hours=3)).isoformat().replace('+00:00', 'Z'), 'value': 0.10},  # Within 6h (min)
            {'start': (now + timedelta(hours=5)).isoformat().replace('+00:00', 'Z'), 'value': 0.25},  # Within 6h (max)
            {'start': (now + timedelta(hours=8)).isoformat().replace('+00:00', 'Z'), 'value': 0.35},  # Outside 6h window
        ]
        
        with patch.object(self.controller, '_get_tariff_data', return_value=mock_rates):
            min_price, max_price, price_spread = self.controller._analyze_prices()
            
            # Should only consider prices within 6 hour window
            self.assertEqual(min_price, 0.10)  # From 3h rate
            self.assertEqual(max_price, 0.25)  # From 5h rate  
            self.assertEqual(price_spread, 15.0)  # (0.25 - 0.10) * 100
            # 0.35 price at 8h should be ignored

    def test_get_solar_forecast_enabled(self):
        """Test solar forecast with enabled window."""
        now = datetime.now(timezone.utc)
        mock_solar_data = [
            {'start': (now + timedelta(hours=1)).isoformat().replace('+00:00', 'Z'), 'value': 2000},  # 2 kW
            {'start': (now + timedelta(hours=2)).isoformat().replace('+00:00', 'Z'), 'value': 3000},  # 3 kW
            {'start': (now + timedelta(hours=25)).isoformat().replace('+00:00', 'Z'), 'value': 1000}, # Outside 24h window
        ]
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'rates': mock_solar_data}
        mock_response.raise_for_status.return_value = None
        self.controller.session.get.return_value = mock_response
        
        forecast = self.controller._get_solar_forecast()
        self.assertEqual(forecast, 5.0)  # 2 + 3 kWh

    def test_get_solar_forecast_disabled(self):
        """Test solar forecast when disabled (hours = 0)."""
        self.controller.config['thresholds']['solar_forecast_hours'] = '0'
        
        forecast = self.controller._get_solar_forecast()
        self.assertEqual(forecast, 0.0)

    def test_get_solar_forecast_not_configured(self):
        """Test solar forecast when API returns 404."""
        mock_response = Mock()
        mock_response.status_code = 404
        self.controller.session.get.return_value = mock_response
        
        forecast = self.controller._get_solar_forecast()
        self.assertEqual(forecast, 0.0)

    def test_set_battery_charge_limit_enable(self):
        """Test setting battery charge limit."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        self.controller.session.post.return_value = mock_response
        
        result = self.controller._set_battery_charge_limit(0.25)
        self.assertTrue(result)
        self.controller.session.post.assert_called_once_with(
            'http://192.168.0.2:7070/api/batterygridchargelimit/0.25',
            timeout=10
        )

    def test_set_battery_charge_limit_disable(self):
        """Test removing battery charge limit."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        self.controller.session.delete.return_value = mock_response
        
        result = self.controller._set_battery_charge_limit(0)
        self.assertTrue(result)
        self.controller.session.delete.assert_called_once_with(
            'http://192.168.0.2:7070/api/batterygridchargelimit',
            timeout=10
        )

    def test_charge_limit_calculation(self):
        """Test charge limit calculation (round up to next cent)."""
        test_cases = [
            (0.1852, 0.19),  # 18.52 cents -> 19 cents
            (0.2000, 0.20),  # 20.00 cents -> 20 cents
            (0.1234, 0.13),  # 12.34 cents -> 13 cents
        ]
        
        for min_price, expected_limit in test_cases:
            calculated_limit = math.ceil(min_price * 100) / 100
            self.assertEqual(calculated_limit, expected_limit)

    def test_run_control_logic_enable_charging(self):
        """Test control logic that should enable charging."""
        # Mock all the required methods
        with patch.object(self.controller, '_authenticate', return_value=True), \
             patch.object(self.controller, '_get_battery_soc', return_value=25), \
             patch.object(self.controller, '_get_current_battery_charge_limit', return_value=0.0), \
             patch.object(self.controller, '_get_solar_forecast', return_value=5.0), \
             patch.object(self.controller, '_analyze_prices', return_value=(0.15, 0.30, 15.0)), \
             patch.object(self.controller, '_set_battery_charge_limit') as mock_set_limit:
            
            self.controller.run_control_logic()
            
            # Should enable charging at 0.15 EUR/kWh (rounded up to 0.15)
            mock_set_limit.assert_called_once_with(0.15)

    def test_run_control_logic_disable_charging(self):
        """Test control logic that should disable charging."""
        # Mock all the required methods
        with patch.object(self.controller, '_authenticate', return_value=True), \
             patch.object(self.controller, '_get_battery_soc', return_value=90), \
             patch.object(self.controller, '_get_current_battery_charge_limit', return_value=0.20), \
             patch.object(self.controller, '_get_solar_forecast', return_value=5.0), \
             patch.object(self.controller, '_analyze_prices', return_value=(0.15, 0.30, 15.0)), \
             patch.object(self.controller, '_set_battery_charge_limit') as mock_set_limit:
            
            self.controller.run_control_logic()
            
            # Should disable charging
            mock_set_limit.assert_called_once_with(0)

    def test_run_control_logic_no_action(self):
        """Test control logic that should take no action."""
        # Mock all the required methods - conditions not met
        with patch.object(self.controller, '_authenticate', return_value=True), \
             patch.object(self.controller, '_get_battery_soc', return_value=50), \
             patch.object(self.controller, '_get_current_battery_charge_limit', return_value=0.0), \
             patch.object(self.controller, '_get_solar_forecast', return_value=20.0), \
             patch.object(self.controller, '_analyze_prices', return_value=(0.15, 0.30, 15.0)), \
             patch.object(self.controller, '_set_battery_charge_limit') as mock_set_limit:
            
            self.controller.run_control_logic()
            
            # Should not call set_battery_charge_limit
            mock_set_limit.assert_not_called()

    def test_run_control_logic_solar_disabled(self):
        """Test control logic with solar forecast disabled."""
        # Set solar forecast hours to 0 (disabled)
        self.controller.config['thresholds']['solar_forecast_hours'] = '0'
        
        with patch.object(self.controller, '_authenticate', return_value=True), \
             patch.object(self.controller, '_get_battery_soc', return_value=25), \
             patch.object(self.controller, '_get_current_battery_charge_limit', return_value=0.0), \
             patch.object(self.controller, '_get_solar_forecast', return_value=0.0), \
             patch.object(self.controller, '_analyze_prices', return_value=(0.15, 0.30, 15.0)), \
             patch.object(self.controller, '_set_battery_charge_limit') as mock_set_limit:
            
            self.controller.run_control_logic()
            
            # Should enable charging even with solar disabled
            mock_set_limit.assert_called_once_with(0.15)

    def test_run_control_logic_insufficient_price_spread(self):
        """Test control logic with insufficient price spread."""
        with patch.object(self.controller, '_authenticate', return_value=True), \
             patch.object(self.controller, '_get_battery_soc', return_value=25), \
             patch.object(self.controller, '_get_current_battery_charge_limit', return_value=0.0), \
             patch.object(self.controller, '_get_solar_forecast', return_value=5.0), \
             patch.object(self.controller, '_analyze_prices', return_value=(0.15, 0.20, 5.0)), \
             patch.object(self.controller, '_set_battery_charge_limit') as mock_set_limit:
            
            self.controller.run_control_logic()
            
            # Should not enable charging due to insufficient price spread (5 < 10)
            mock_set_limit.assert_not_called()

    def test_run_control_logic_authentication_failure(self):
        """Test control logic when authentication fails."""
        with patch.object(self.controller, '_authenticate', return_value=False), \
             patch.object(self.controller, '_set_battery_charge_limit') as mock_set_limit:
            
            self.controller.run_control_logic()
            
            # Should not proceed with any actions
            mock_set_limit.assert_not_called()

    def test_edge_cases_empty_price_data(self):
        """Test edge case with empty price data in the time window."""
        # Mock rates that are all outside the 24-hour window
        past_time = datetime.now(timezone.utc) - timedelta(hours=25)
        mock_rates = [
            {'start': past_time.isoformat().replace('+00:00', 'Z'), 'value': 0.15}
        ]
        
        with patch.object(self.controller, '_get_tariff_data', return_value=mock_rates):
            min_price, max_price, price_spread = self.controller._analyze_prices()
            
            self.assertEqual(min_price, 0.0)
            self.assertEqual(max_price, 0.0)
            self.assertEqual(price_spread, 0.0)

    def test_edge_cases_timezone_handling(self):
        """Test timezone handling for rates without timezone info."""
        now = datetime.now(timezone.utc)
        # Create a rate without timezone info
        mock_rates = [
            {'start': '2025-09-08T10:00:00', 'value': 0.15}  # No timezone
        ]
        
        with patch.object(self.controller, '_get_tariff_data', return_value=mock_rates):
            # Should handle timezone-naive datetime gracefully
            min_price, max_price, price_spread = self.controller._analyze_prices()
            # The exact result depends on the current time, but it shouldn't crash
            self.assertIsInstance(min_price, float)


class TestEVCCBatteryControllerIntegration(unittest.TestCase):
    """Integration tests that test the controller with realistic scenarios."""

    def setUp(self):
        """Set up integration test fixtures."""
        # Create a temporary config file
        self.temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False)
        test_config = """
[evcc]
host = 192.168.0.2
port = 7070
password = 

[thresholds]
battery_low_soc = 30
battery_high_soc = 85
min_solar_forecast = 10
solar_forecast_hours = 24
price_analysis_hours = 12
min_price_spread = 10

[logging]
level = DEBUG
file = /tmp/test_evcc_battery_controller.log
"""
        self.temp_config.write(test_config)
        self.temp_config.close()
        
        self.controller = EVCCBatteryController(self.temp_config.name)
        self.controller.session = Mock()

    def tearDown(self):
        """Clean up integration test fixtures."""
        os.unlink(self.temp_config.name)

    def test_realistic_evening_scenario(self):
        """Test realistic evening scenario: low battery, little solar left, good prices."""
        # Evening time
        now = datetime.now(timezone.utc).replace(hour=20, minute=0, second=0, microsecond=0)
        
        # Mock system state: low battery, no current limit
        state_data = {'batterySoc': 25, 'batteryGridChargeLimit': None}
        
        # Mock price data: good spread with low overnight prices
        price_data = [
            {'start': (now + timedelta(hours=1)).isoformat().replace('+00:00', 'Z'), 'value': 0.12},  # 22:00
            {'start': (now + timedelta(hours=2)).isoformat().replace('+00:00', 'Z'), 'value': 0.10},  # 23:00 (min)
            {'start': (now + timedelta(hours=3)).isoformat().replace('+00:00', 'Z'), 'value': 0.11},  # 00:00
            {'start': (now + timedelta(hours=10)).isoformat().replace('+00:00', 'Z'), 'value': 0.35}, # 07:00 (max)
        ]
        
        # Mock solar data: very little remaining for today
        solar_data = [
            {'start': (now + timedelta(hours=1)).isoformat().replace('+00:00', 'Z'), 'value': 0},     # 22:00
            {'start': (now + timedelta(hours=10)).isoformat().replace('+00:00', 'Z'), 'value': 1000}, # 07:00 next day
        ]
        
        with patch.object(self.controller, '_authenticate', return_value=True), \
             patch.object(self.controller, '_get_state', return_value=state_data), \
             patch.object(self.controller, '_get_tariff_data', return_value=price_data), \
             patch('datetime.datetime') as mock_datetime:
            
            # Mock datetime.now to return our evening time
            mock_datetime.now.return_value = now
            mock_datetime.fromisoformat = datetime.fromisoformat
            mock_datetime.combine = datetime.combine
            mock_datetime.max = datetime.max
            
            # Mock solar API response
            mock_solar_response = Mock()
            mock_solar_response.status_code = 200
            mock_solar_response.json.return_value = {'rates': solar_data}
            mock_solar_response.raise_for_status.return_value = None
            
            def mock_get(url, **kwargs):
                if 'tariff/solar' in url:
                    return mock_solar_response
                else:  # tariff/grid
                    mock_price_response = Mock()
                    mock_price_response.status_code = 200
                    mock_price_response.json.return_value = {'rates': price_data}
                    mock_price_response.raise_for_status.return_value = None
                    return mock_price_response
            
            self.controller.session.get.side_effect = mock_get
            
            # Mock the post call for setting charge limit
            mock_post_response = Mock()
            mock_post_response.raise_for_status.return_value = None
            self.controller.session.post.return_value = mock_post_response
            
            # Run the control logic
            with patch('datetime.datetime', mock_datetime):
                self.controller.run_control_logic()
            
            # Should enable charging at the minimum price (0.10 EUR/kWh)
            self.controller.session.post.assert_called_once_with(
                'http://192.168.0.2:7070/api/batterygridchargelimit/0.1',
                timeout=10
            )


if __name__ == '__main__':
    # Create a test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestEVCCBatteryController))
    suite.addTests(loader.loadTestsFromTestCase(TestEVCCBatteryControllerIntegration))
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with proper code
    sys.exit(0 if result.wasSuccessful() else 1)
