#!/usr/bin/env python3
"""
Test script for EVCC Battery Charging Controller

This script tests the connection to EVCC and displays current status
without making any changes to the system.
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from battery_charging_controller import EVCCBatteryController


def test_connection():
    """Test connection and display current status."""
    print("=== EVCC Battery Controller Test ===")
    
    try:
        controller = EVCCBatteryController()
        
        # Test authentication
        print("Testing authentication...")
        if controller._authenticate():
            print("✓ Authentication successful")
        else:
            print("✗ Authentication failed")
            return
        
        # Test getting system state
        print("\nTesting system state retrieval...")
        try:
            state = controller._get_state()
            print("✓ System state retrieved successfully")
            print(f"State keys: {list(state.keys())[:10]}...")  # Show first 10 keys
        except Exception as e:
            print(f"✗ Failed to get system state: {e}")
            
            # Try to get raw response for debugging
            try:
                import requests
                response = requests.get(f"{controller.base_url}/state", timeout=10)
                print(f"Raw response status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"Response structure: {type(data)} with keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            except Exception as debug_e:
                print(f"Debug request also failed: {debug_e}")
            return
        
        # Display current status
        print("\n=== Current Status ===")
        
        # Battery SoC
        battery_soc = controller._get_battery_soc()
        print(f"Battery SoC: {battery_soc}%")
        
        # Current charge limit
        charge_limit = controller._get_current_battery_charge_limit()
        if charge_limit > 0:
            print(f"Battery charge limit: {charge_limit} cents/kWh (ACTIVE)")
        else:
            print("Battery charge limit: Not set")
        
        # Solar forecast
        solar_forecast = controller._get_solar_forecast()
        print(f"Remaining solar forecast (today): {solar_forecast:.1f} kWh")
        
        # Price analysis
        min_price, max_price, price_spread = controller._analyze_prices()
        if price_spread > 0:
            print(f"Price analysis:")
            print(f"  Min price: {min_price:.4f} EUR/kWh")
            print(f"  Max price: {max_price:.4f} EUR/kWh")
            print(f"  Price spread: {price_spread:.2f} cents/kWh")
        else:
            print("Price data: Not available")
        
        # Load configuration thresholds
        config = controller.config
        print(f"\n=== Configuration Thresholds ===")
        print(f"Low SoC threshold: {config['thresholds']['battery_low_soc']}%")
        print(f"High SoC threshold: {config['thresholds']['battery_high_soc']}%")
        print(f"Min solar forecast: {config['thresholds']['min_solar_forecast']} kWh")
        print(f"Min price spread: {config['thresholds']['min_price_spread']} cents/kWh")
        
        # Evaluate conditions
        print(f"\n=== Condition Evaluation ===")
        low_soc = battery_soc < float(config['thresholds']['battery_low_soc'])
        no_limit = charge_limit <= 0
        low_solar = solar_forecast < float(config['thresholds']['min_solar_forecast'])
        good_spread = price_spread > float(config['thresholds']['min_price_spread'])
        high_soc = battery_soc > float(config['thresholds']['battery_high_soc'])
        limit_set = charge_limit > 0
        
        print(f"Battery SoC < {config['thresholds']['battery_low_soc']}%: {'✓' if low_soc else '✗'}")
        print(f"No charge limit set: {'✓' if no_limit else '✗'}")
        print(f"Solar forecast < {config['thresholds']['min_solar_forecast']} kWh: {'✓' if low_solar else '✗'}")
        print(f"Price spread > {config['thresholds']['min_price_spread']} cents: {'✓' if good_spread else '✗'}")
        
        print(f"\nEnable charging conditions: {'✓ MET' if (low_soc and no_limit and low_solar and good_spread) else '✗ Not met'}")
        print("Logic: Low battery + No limit + Little remaining solar + Good price spread")
        
        print(f"Battery SoC > {config['thresholds']['battery_high_soc']}%: {'✓' if high_soc else '✗'}")
        print(f"Charge limit currently set: {'✓' if limit_set else '✗'}")
        
        print(f"Disable charging conditions: {'✓ MET' if (high_soc and limit_set) else '✗ Not met'}")
        
        print("\n=== Test Completed Successfully ===")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    test_connection()
