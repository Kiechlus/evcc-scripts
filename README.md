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

Since there's no pre-built EVCC image for Raspberry Pi, the installation follows the standard Linux installation process as documented at [docs.evcc.io](https://docs.evcc.io/docs/installation/linux). The installation process works seamlessly on Raspberry Pi 3B.

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
   - Alternatively, use the [Sunny Portal](https://ennexos.sunnyportal.com/) to view device parameters

2. **SMA Sunny Home Manager**: 
   - The MAC address is printed on the device label
   - Location: Right side of the physical device


