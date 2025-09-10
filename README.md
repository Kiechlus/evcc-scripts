# EVCC Scripts

This repository contains scripts and documentation for working with the excellent [evcc.io](https://evcc.io) energy management system (EMS).

## Table of Contents

- [Overview](#overview)
- [Installation on Raspberry Pi 3B](#installation-on-raspberry-pi-3b)
  - [Hardware Choice](#hardware-choice)
  - [Installation Process](#installation-process)
  - [Power Optimization](#power-optimization)
  - [Network Configuration](#network-configuration)
- [Secure Remote Access](#secure-remote-access)
  - [Remote Access Overview](#remote-access-overview)
  - [Cloudflare Tunnel Setup](#cloudflare-tunnel-setup)
  - [Nginx Reverse Proxy with Basic Auth](#nginx-reverse-proxy-with-basic-auth)
  - [Complete Configuration](#complete-configuration)
  - [Security Considerations](#security-considerations)
- [Battery Charging Controller](#battery-charging-controller)
  - [Controller Overview](#controller-overview)
  - [Features](#features)
  - [Algorithm](#algorithm)
  - [Installation](#installation)
  - [Configuration](#configuration)
  - [Testing](#testing)
  - [Unit Testing](#unit-testing)
  - [Monitoring](#monitoring)
  - [Files](#files)
- [How-To Guides](#how-to-guides)
  - [Log Analysis](#log-analysis)
  - [Phase Switching Investigation](#phase-switching-investigation)
  - [Troubleshooting](#troubleshooting)

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

## Secure Remote Access

### Remote Access Overview

This section describes how to securely expose your EVCC installation to the internet using Cloudflare tunnels and nginx reverse proxy with basic authentication. This setup provides:

- **Zero Trust Security**: No open ports on your home network
- **SSL/TLS Encryption**: Automatic HTTPS with Cloudflare certificates
- **Basic Authentication**: Username/password protection
- **WebSocket Support**: Full compatibility with EVCC's real-time features
- **DDoS Protection**: Cloudflare's built-in protection

### Cloudflare Tunnel Setup

#### Prerequisites

- Cloudflare account with a domain (free tier works)
- Domain DNS managed by Cloudflare
- `cloudflared` installed on your Raspberry Pi

#### Step 1: Install Cloudflared

```bash
# Download and install cloudflared
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i cloudflared-linux-arm64.deb
```

#### Step 2: Authenticate with Cloudflare

```bash
# Login to Cloudflare (opens browser)
cloudflared tunnel login
```

This will save your credentials to `/home/kiechlus/.cloudflared/cert.pem`.

#### Step 3: Create Tunnel

```bash
# Create a tunnel named 'evcc'
cloudflared tunnel create evcc
```

This creates a tunnel and saves credentials to `/home/kiechlus/.cloudflared/<tunnel-id>.json`.

#### Step 4: Configure DNS

```bash
# Create DNS record pointing to your tunnel
cloudflared tunnel route dns evcc evcc.yourdomain.org
```

Alternatively, manually create a CNAME record in Cloudflare Dashboard:
- **Type**: CNAME
- **Name**: evcc
- **Target**: `<tunnel-id>.cfargotunnel.com`
- **Proxy Status**: Proxied (orange cloud)

#### Step 5: Create Tunnel Configuration

```bash
# Create configuration directory
sudo mkdir -p /etc/cloudflared

# Create tunnel configuration
sudo nano /etc/cloudflared/config.yml
```

Add the following configuration:

```yaml
tunnel: evcc
credentials-file: /home/kiechlus/.cloudflared/<your-tunnel-id>.json

ingress:
  - hostname: evcc.yourdomain.org
    service: http://localhost:80  # Points to nginx
  - service: http_status:404
```

Replace `<your-tunnel-id>` with your actual tunnel ID.

### Nginx Reverse Proxy with Basic Auth

#### Step 1: Install Nginx and Tools

```bash
sudo apt update
sudo apt install nginx apache2-utils -y
```

#### Step 2: Create User Accounts

```bash
# Create password file with first user
sudo htpasswd -c /etc/nginx/.evcc_passwd user1

# Add additional users
sudo htpasswd /etc/nginx/.evcc_passwd user2
sudo htpasswd /etc/nginx/.evcc_passwd user3
```

#### Step 3: Configure Nginx

Create nginx configuration:

```bash
sudo nano /etc/nginx/sites-available/evcc
```

Add the following configuration:

```nginx
server {
    listen 80;
    server_name evcc.yourdomain.org;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    location / {
        # Basic Authentication
        auth_basic "EVCC Access - Restricted";
        auth_basic_user_file /etc/nginx/.evcc_passwd;

        # Proxy settings
        proxy_pass http://localhost:7070;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket Support (essential for EVCC)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

#### Step 4: Enable Site

```bash
# Enable the site
sudo ln -s /etc/nginx/sites-available/evcc /etc/nginx/sites-enabled/

# Test nginx configuration
sudo nginx -t

# Restart nginx
sudo systemctl restart nginx
```

### Complete Configuration

#### Step 1: Create Systemd Service

```bash
sudo nano /etc/systemd/system/cloudflared-evcc.service
```

Add the following service configuration:

```ini
[Unit]
Description=Cloudflare Tunnel for EVCC
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=kiechlus
ExecStart=/usr/local/bin/cloudflared tunnel run evcc
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Step 2: Enable and Start Services

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable and start cloudflared service
sudo systemctl enable --now cloudflared-evcc

# Ensure nginx is running
sudo systemctl enable --now nginx

# Check service status
sudo systemctl status cloudflared-evcc
sudo systemctl status nginx
```

#### Step 3: Monitor Logs

```bash
# Watch cloudflared logs
sudo journalctl -u cloudflared-evcc -f

# Watch nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

#### Step 4: Test the Setup

1. Wait a few minutes for DNS propagation
2. Visit `https://evcc.yourdomain.org`
3. Enter your username and password
4. Verify EVCC loads correctly with real-time updates

### Security Considerations

#### Network Security

- **No Open Ports**: Cloudflare tunnel requires no inbound firewall rules
- **Zero Trust**: All traffic flows through Cloudflare's edge network
- **DDoS Protection**: Automatic protection against attacks

#### Authentication Security

```bash
# Secure the password file
sudo chmod 600 /etc/nginx/.evcc_passwd
sudo chown root:root /etc/nginx/.evcc_passwd

# Regular password rotation
sudo htpasswd /etc/nginx/.evcc_passwd username
```

## Battery Charging Controller

### Controller Overview

The repository includes an battery charging controller that automatically manages grid charging of the home battery based on dynamic pricing, battery state, and solar forecasts.

### Features

- **Automated Grid Charging**: Charges battery from grid during low-price periods
- **Configurable Thresholds**: Customizable SoC levels, price spreads, and solar forecasts
- **Safety Limits**: Prevents overcharging and respects high SoC limits
- **Logging**: Detailed logs of all decisions and actions
- **Easy Setup**: Automated installation and cron job configuration

### Algorithm

The controller implements the following logic:

**Enable Grid Chargingat cheapest price when:**
- Battery SoC < 30% (configurable)
- No charging limit currently set (≤ 0 cents)
- Solar forecast for next X hours < 10 kWh (configurable window and threshold)
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
min_solar_forecast = 10     # Minimum solar forecast (kWh)
solar_forecast_hours = 24   # Solar forecast window (hours, 0=disabled)
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

### Unit Testing

The controller includes comprehensive unit tests with mocked API calls for reliable testing:

```bash
# Run all unit tests
python3 test_battery_charging_controller.py

# Run with test runner script (includes virtual environment setup)
./run_tests.sh

# Run with pytest (if installed)
pip3 install pytest pytest-cov
pytest test_battery_charging_controller.py -v
```

#### Test Coverage

The test suite includes:

- **Configuration Tests**: Validate config file loading and parameter handling
- **Authentication Tests**: Mock successful and failed authentication scenarios
- **API Integration Tests**: Mock all EVCC API calls (state, tariff, solar forecast)
- **Logic Tests**: Test all decision-making scenarios with various conditions
- **Edge Case Tests**: Handle missing data, timezone issues, and error conditions
- **Integration Tests**: Full end-to-end scenarios with realistic data

#### Test Files

- `test_battery_charging_controller.py` - Comprehensive unit test suite
- `requirements-test.txt` - Testing dependencies
- `pytest.ini` - Pytest configuration with coverage reporting
- `run_tests.sh` - Automated test runner with virtual environment

#### Running Specific Tests

```bash
# Run only unit tests
python3 -m unittest TestEVCCBatteryController -v

# Run only integration tests
python3 -m unittest TestEVCCBatteryControllerIntegration -v

# Run specific test method
python3 -m unittest TestEVCCBatteryController.test_run_control_logic_enable_charging -v
```

### Files

- `battery_charging_controller.py` - Main controller script
- `battery_config.ini` - Configuration file
- `test_battery_controller.py` - Connection and status test script (live system)
- `test_battery_charging_controller.py` - Unit test suite with mocked APIs
- `setup_battery_controller.sh` - Automated setup script
- `run_tests.sh` - Test runner script
  

## How-To Guides

### Log Analysis

EVCC generates detailed logs that can be invaluable for troubleshooting and understanding system behavior.

#### Accessing EVCC Logs

See https://docs.evcc.io/en/docs/faq#how-do-i-create-a-log-file-for-error-analysis.

Extract logs from the system journal:

```bash
# Export all EVCC logs to a file
sudo journalctl -u evcc -q > ~/evcc.log

# Export logs from the last 24 hours
sudo journalctl -u evcc --since "24 hours ago" -q > ~/evcc_recent.log

# Follow live logs
sudo journalctl -u evcc -f
```

#### Searching Through Logs

Large log files can be efficiently searched using vim:

```bash
# Open log file in vim
vim ~/evcc.log

# Search for specific terms:
# 1. Press '/' to enter search mode
# 2. Type your search term (e.g., "error", "phase", "battery")
# 3. Press Enter to search
# 4. Navigate results:
#    - 'n' for next match
#    - 'N' for previous match
#    - 'q' to quit vim
```

#### Useful Search Terms

Common search patterns for log analysis:

```bash
# Error investigation
/error
/warning
/failed

# Battery-related events
/battery
/soc
/charge

# Phase switching behavior
/phase
/scale3p
/available power

# Network and API issues
/timeout
/connection
/api
```

### Phase Switching Investigation

Understanding phase switching behavior in three-phase systems:

#### Key Log Indicators

Look for these patterns when investigating phase switching:

```
start phase scale3p timer
phaseScale3p in 30s
available power ... > ... threshold
```

#### Analysis Process

1. **Identify Phase Events**:
   ```bash
   # Search for phase-related logs
   grep -i "phase\|scale3p" ~/evcc.log
   ```

2. **Check Power Thresholds**:
   ```bash
   # Look for power threshold events
   grep -i "available power\|threshold" ~/evcc.log
   ```

3. **Timeline Analysis**:
   ```bash
   # Extract timestamps for phase events
   grep -i "scale3p timer" ~/evcc.log | cut -d' ' -f1-2
   ```

### Troubleshooting

#### Common Issues and Solutions

**Battery Controller Not Working**:
1. Check EVCC API connectivity:
   ```bash
   python3 test_battery_controller.py
   ```
2. Verify cron job is running:
   ```bash
   crontab -l
   sudo systemctl status cron
   ```
3. Check controller logs:
   ```bash
   tail -f /var/log/evcc_battery_controller.log
   ```

**EVCC Service Issues**:
1. Check service status:
   ```bash
   sudo systemctl status evcc
   ```
2. Restart service:
   ```bash
   sudo systemctl restart evcc
   ```
3. Check configuration:
   ```bash
   evcc -c /etc/evcc.yaml check
   ```

**Network Connectivity Issues**:
1. Test device connectivity:
   ```bash
   # Test wallbox connection
   ping <wallbox-ip>
   
   # Test SMA inverter
   ping <inverter-ip>
   
   # Test API endpoints
   curl -s http://<evcc-host>:7070/api/state
   ```

#### Log File Locations

- **EVCC Main Logs**: `sudo journalctl -u evcc`
- **Battery Controller**: `/var/log/evcc_battery_controller.log`
- **System Logs**: `/var/log/syslog`
- **Cron Logs**: `/var/log/cron.log`

#### Debug Mode

Enable debug logging for detailed troubleshooting:

1. **EVCC Debug Mode**:
   ```bash
   # Edit EVCC config
   sudo nano /etc/evcc.yaml
   
   # Add or modify log level
   log: debug
   ```

2. **Battery Controller Debug**:
   ```bash
   # Edit controller config
   nano battery_config.ini
   
   # Set log level to DEBUG
   [logging]
   level = DEBUG
   ```

3. **Restart Services**:
   ```bash
   sudo systemctl restart evcc
   # Battery controller will pick up new config on next run
   ```



