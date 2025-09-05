#!/bin/bash

# EVCC Battery Charging Controller Setup Script
# This script installs dependencies and sets up the cron job

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/battery_charging_controller.py"
CONFIG_FILE="$SCRIPT_DIR/battery_config.ini"
LOG_FILE="/var/log/evcc_battery_controller.log"

echo "=== EVCC Battery Charging Controller Setup ==="

# Check if running as root for system-wide installation
if [[ $EUID -eq 0 ]]; then
    echo "Running as root - will install system-wide"
    USE_SUDO=""
else
    echo "Running as regular user - will use sudo for system operations"
    USE_SUDO="sudo"
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install --user requests configparser

# Create log directory and file
echo "Setting up logging..."
$USE_SUDO touch "$LOG_FILE"
$USE_SUDO chmod 666 "$LOG_FILE"

# Make the Python script executable
chmod +x "$PYTHON_SCRIPT"

# Create the cron job entry
CRON_ENTRY="*/5 * * * * cd $SCRIPT_DIR && /usr/bin/python3 $PYTHON_SCRIPT >> $LOG_FILE 2>&1"

echo "Setting up cron job..."
echo "The following cron job will be added (runs every 5 minutes):"
echo "$CRON_ENTRY"
echo ""
read -p "Do you want to add this cron job? (y/N): " confirm

if [[ $confirm =~ ^[Yy]$ ]]; then
    # Add the cron job
    (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
    echo "Cron job added successfully!"
    echo ""
    echo "To view current cron jobs: crontab -l"
    echo "To edit cron jobs: crontab -e"
    echo "To remove the cron job, edit with 'crontab -e' and delete the line"
else
    echo "Cron job not added. You can add it manually later with:"
    echo "crontab -e"
    echo "Then add the line:"
    echo "$CRON_ENTRY"
fi

echo ""
echo "=== Setup Instructions ==="
echo "1. Review and edit the configuration file: $CONFIG_FILE"
echo "2. Update your EVCC host IP address and port if needed"
echo "3. Adjust the threshold values according to your preferences"
echo "4. Test the script manually: python3 $PYTHON_SCRIPT"
echo "5. Check the log file for output: tail -f $LOG_FILE"
echo ""
echo "=== Configuration Guidelines ==="
echo "• battery_low_soc: SoC level below which charging should be considered (default: 30%)"
echo "• battery_high_soc: SoC level above which charging should stop (default: 85%)"
echo "• min_solar_forecast: Minimum expected solar generation for next day (default: 10 kWh)"
echo "• min_price_spread: Minimum price difference required to enable charging (default: 10 cents/kWh)"
echo ""
echo "The script will:"
echo "• Check conditions every 5 minutes"
echo "• Enable battery charging from grid when:"
echo "  - Battery SoC < 30%"
echo "  - No charging limit currently set"
echo "  - Solar forecast < 10 kWh"
echo "  - Price spread > 10 cents/kWh"
echo "• Disable battery charging when:"
echo "  - Battery SoC > 85%"
echo "  - Charging limit is currently set"
echo ""
echo "Setup complete!"
