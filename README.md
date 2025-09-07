# EVCC Scripts

This repository contains scripts and documentation for working with the excellent [evcc.io](https://evcc.io) energy management system (EMS).

## Overview

EVCC is an open-source energy management system that helps optimize the use of solar energy by intelligently controlling electric vehicle charging and other loads.

## Installation on Raspberry Pi 3B

### Hardware Choice

The Raspberry Pi 3B was chosen over newer models for this installation due to:
- Lower cost
- Reduced power consumption
- Sufficient performance for EVCC requirements

### Installation Process

Since there's no pre-built EVCC image for Raspberry Pi 3, the installation follows the standard Linux installation process as documented at [docs.evcc.io](https://docs.evcc.io/docs/installation/linux). The installation process works seamlessly on Raspberry Pi 3B.

### Power Optimization

#### Disable WiFi and Bluetooth

To minimize power consumption, disable unused wireless features:

1. Edit the boot configuration:
   ```bash
   sudo nano /boot/config.txt
   ```

2. Add the following lines to the end of the file:
   ```
   # Disable WiFi and Bluetooth to reduce power consumption
   dtoverlay=disable-wifi
   dtoverlay=disable-bt
   ```

3. Save the file and reboot:
   ```bash
   sudo reboot
   ```

### Network Configuration

#### Configure Static IP Address for Raspberry Pi

Setting up a static IP address ensures reliable network connectivity:

1. Edit the DHCP configuration:
   ```bash
   sudo vim /etc/dhcpcd.conf
   ```

2. Add the following configuration (adjust IP addresses to match your network):
   ```
   interface eth0
   static ip_address=192.168.0.2/24
   static routers=192.168.0.1
   static domain_name_servers=192.168.0.1
   ```

#### Configure Static IP Addresses for SMA Products and Wallbox

**Purpose**: Static IP addresses ensure robust EVCC configuration that isn't affected by changing DHCP assignments.

**Implementation**: Most routers support binding IP addresses to MAC addresses through DHCP reservations.

**Challenge with SMA Devices**: 
- SMA Sunny Home Manager and hybrid inverter MAC addresses may not display correctly in router DHCP tables
- Both devices might show identical MAC addresses in the router interface

**Solution for Finding MAC Addresses**:

1. **SMA Inverter**: 
   - Access the inverter's web interface directly
   - Find MAC addresses for WLAN and LAN interfaces in the device parameters

2. **SMA Sunny Home Manager**: 
   - The MAC address is printed on the device label
   - Location: Right side of the device

## Battery Charging Controller

### Overview

The repository includes an battery charging controller that automatically manages grid charging based on dynamic pricing, battery state, and solar forecasts.

### Features

- **Automated Grid Charging**: Charges battery from grid during low-price periods
- **Configurable Thresholds**: Customizable SoC levels, price spreads, and solar forecasts
- **Safety Limits**: Prevents overcharging and respects high SoC limits
- **Logging**: Detailed logs of all decisions and actions
- **Easy Setup**: Automated installation and cron job configuration

### Algorithm

The controller implements the following logic:

**Enable Grid Charging When:**
- Battery SoC < 30% (configurable)
- No charging limit currently set (≤ 0 cents)
- Solar forecast for next 12 hours < 10 kWh (configurable)
- Price spread (max - min) > 10 cents/kWh (configurable)

**Disable Grid Charging When:**
- Battery SoC > 85% (configurable)
- Charging limit is currently active

### Installation

1. **Automatic Setup** (Recommended):
   ```bash
   ./setup_battery_controller.sh
   ```

2. **Manual Setup**:
   ```bash
   # Install dependencies
   pip3 install --user requests configparser
   
   # Edit configuration
   nano battery_config.ini
   
   # Test the script
   python3 test_battery_controller.py
   
   # Add to crontab (runs every 5 minutes)
   crontab -e
   # Add: */5 * * * * cd /home/kiechle/git/evcc-scripts && /usr/bin/python3 battery_charging_controller.py >> /var/log/evcc_battery_controller.log 2>&1
   ```

### Configuration

Edit `battery_config.ini` to customize:

```ini
[evcc]
host = 192.168.0.2          # Your EVCC host IP
port = 7070                 # EVCC port
password =                  # EVCC password (if required)

[thresholds]
battery_low_soc = 30        # Low SoC threshold (%)
battery_high_soc = 85       # High SoC threshold (%)
min_solar_forecast = 10     # Minimum solar forecast (12h) (kWh)
min_price_spread = 10       # Minimum price spread (cents/kWh)
```

### Testing

Test your configuration and connection:

```bash
python3 test_battery_controller.py
```

### Monitoring

View controller activity:

```bash
# View recent activity
tail -f /var/log/evcc_battery_controller.log

# Check cron job status
crontab -l
```

### Files

- `battery_charging_controller.py` - Main controller script
- `battery_config.ini` - Configuration file
- `test_battery_controller.py` - Connection and status test script
- `setup_battery_controller.sh` - Automated setup script
  


