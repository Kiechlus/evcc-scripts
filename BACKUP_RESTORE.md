# EVCC System Backup & Restore Guide

This guide covers backing up and restoring all critical system files, configurations, and data for your EVCC installation on Raspberry Pi.

## Table of Contents

- [Quick Backup Script](#quick-backup-script)
- [Complete System Backup](#complete-system-backup)
- [Individual Component Backups](#individual-component-backups)
  - [EVCC Configuration](#evcc-configuration)
  - [Battery Controller](#battery-controller)
  - [Cloudflare Tunnel](#cloudflare-tunnel)
  - [Nginx Configuration](#nginx-configuration)
  - [SSH Configuration](#ssh-configuration)
  - [System Logs](#system-logs)
  - [Cron Jobs](#cron-jobs)
  - [Network Configuration](#network-configuration)
  - [Shell History](#shell-history)
  - [Systemd Services](#systemd-services)
- [Restore Procedures](#restore-procedures)
- [Automated Backup Setup](#automated-backup-setup)

## Quick Backup Script

Create a comprehensive backup script for all essential files:

```bash
#!/bin/bash
# evcc-backup.sh - Complete EVCC system backup

BACKUP_DIR="/home/kiechlus/backups/evcc-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "🔄 Creating EVCC system backup in $BACKUP_DIR"

# EVCC Configuration & Data
sudo cp -r /etc/evcc* "$BACKUP_DIR/" 2>/dev/null || true
sudo cp /etc/systemd/system/evcc.service "$BACKUP_DIR/evcc.service" 2>/dev/null || true

# Battery Controller
cp -r ~/evcc-scripts "$BACKUP_DIR/evcc-scripts" 2>/dev/null || true
crontab -l > "$BACKUP_DIR/crontab_kiechlus.txt" 2>/dev/null || true

# Cloudflare Tunnel
sudo cp -r /etc/cloudflared "$BACKUP_DIR/cloudflared" 2>/dev/null || true
cp -r ~/.cloudflared "$BACKUP_DIR/cloudflared_user" 2>/dev/null || true
sudo cp /etc/systemd/system/cloudflared*.service "$BACKUP_DIR/" 2>/dev/null || true

# Nginx Configuration
sudo cp -r /etc/nginx/sites-available "$BACKUP_DIR/nginx_sites-available" 2>/dev/null || true
sudo cp -r /etc/nginx/sites-enabled "$BACKUP_DIR/nginx_sites-enabled" 2>/dev/null || true
sudo cp /etc/nginx/.evcc_passwd "$BACKUP_DIR/nginx_evcc_passwd" 2>/dev/null || true
sudo cp /etc/nginx/nginx.conf "$BACKUP_DIR/nginx.conf" 2>/dev/null || true

# SSH Configuration
cp ~/.ssh/config "$BACKUP_DIR/ssh_config" 2>/dev/null || true
cp ~/.ssh/id_* "$BACKUP_DIR/" 2>/dev/null || true
cp ~/.ssh/known_hosts* "$BACKUP_DIR/" 2>/dev/null || true

# Network Configuration
sudo cp /etc/dhcpcd.conf "$BACKUP_DIR/dhcpcd.conf" 2>/dev/null || true
sudo cp -r /etc/netplan "$BACKUP_DIR/netplan" 2>/dev/null || true
sudo cp /etc/wpa_supplicant/wpa_supplicant.conf "$BACKUP_DIR/wpa_supplicant.conf" 2>/dev/null || true

# Shell History & Environment
cp ~/.bashrc "$BACKUP_DIR/bashrc" 2>/dev/null || true
cp ~/.bash_history "$BACKUP_DIR/bash_history" 2>/dev/null || true
cp ~/.profile "$BACKUP_DIR/profile" 2>/dev/null || true
cp ~/.bash_aliases "$BACKUP_DIR/bash_aliases" 2>/dev/null || true

# System Services & Logs
sudo systemctl list-enabled --no-pager > "$BACKUP_DIR/enabled_services.txt"
sudo journalctl --list-boots --no-pager > "$BACKUP_DIR/boot_history.txt"
sudo cp /etc/systemd/journald.conf "$BACKUP_DIR/journald.conf" 2>/dev/null

# Export recent logs (last 7 days)
sudo journalctl -u evcc --since "7 days ago" --no-pager > "$BACKUP_DIR/evcc_logs_7days.log" 2>/dev/null
sudo journalctl -u cloudflared-evcc --since "7 days ago" --no-pager > "$BACKUP_DIR/cloudflared_logs_7days.log" 2>/dev/null
sudo journalctl -u nginx --since "7 days ago" --no-pager > "$BACKUP_DIR/nginx_logs_7days.log" 2>/dev/null

# Battery controller logs
cp ~/evcc_battery_controller.log* "$BACKUP_DIR/" 2>/dev/null
sudo cp /var/log/evcc_battery_controller.log* "$BACKUP_DIR/" 2>/dev/null

# System Information
uname -a > "$BACKUP_DIR/system_info.txt"
cat /etc/os-release > "$BACKUP_DIR/os_release.txt"
df -h > "$BACKUP_DIR/disk_usage.txt"
free -h > "$BACKUP_DIR/memory_info.txt"
ip addr show > "$BACKUP_DIR/network_interfaces.txt"

# Package Lists
dpkg --get-selections > "$BACKUP_DIR/installed_packages.txt"
pip3 list > "$BACKUP_DIR/python_packages.txt" 2>/dev/null

# Create archive
cd "$(dirname "$BACKUP_DIR")"
tar -czf "$(basename "$BACKUP_DIR").tar.gz" "$(basename "$BACKUP_DIR")"

echo "✅ Backup completed: $BACKUP_DIR.tar.gz"
echo "📂 Size: $(du -sh "$BACKUP_DIR.tar.gz" | cut -f1)"
```

## Complete System Backup

### Create the backup script:

```bash
# Download and make executable
curl -o ~/evcc-backup.sh https://raw.githubusercontent.com/Kiechlus/evcc-scripts/main/evcc-backup.sh
chmod +x ~/evcc-backup.sh

# Run backup
~/evcc-backup.sh
```

### Manual complete backup:

```bash
# Create backup directory
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/kiechlus/backups/evcc-complete-$BACKUP_DATE"
mkdir -p "$BACKUP_DIR"

# Full system backup (warning: large!)
sudo rsync -av --exclude='/proc' --exclude='/sys' --exclude='/dev' \
  --exclude='/tmp' --exclude='/var/tmp' --exclude='/run' \
  / "$BACKUP_DIR/system_root/" 2>/dev/null

# Create compressed archive
sudo tar -czf "$BACKUP_DIR.tar.gz" -C "$(dirname "$BACKUP_DIR")" "$(basename "$BACKUP_DIR")"
```

## Individual Component Backups

### EVCC Configuration

```bash
# Backup EVCC config
sudo cp -r /etc/evcc* ~/backups/evcc-config-$(date +%Y%m%d)/
sudo cp /etc/systemd/system/evcc.service ~/backups/evcc-config-$(date +%Y%m%d)/

# Export EVCC logs (last 30 days)
sudo journalctl -u evcc --since "30 days ago" --no-pager > ~/backups/evcc-logs-$(date +%Y%m%d).log

# Backup EVCC database (if exists)
sudo cp /var/lib/evcc/* ~/backups/evcc-data-$(date +%Y%m%d)/ 2>/dev/null
```

### Battery Controller

```bash
# Backup battery controller files
cp -r ~/evcc-scripts ~/backups/evcc-scripts-$(date +%Y%m%d)/

# Export cron jobs
crontab -l > ~/backups/crontab-$(date +%Y%m%d).txt

# Backup controller logs
cp ~/evcc_battery_controller.log* ~/backups/ 2>/dev/null
sudo cp /var/log/evcc_battery_controller.log* ~/backups/ 2>/dev/null
```

### Cloudflare Tunnel

```bash
# Backup Cloudflare tunnel config
sudo cp -r /etc/cloudflared ~/backups/cloudflared-$(date +%Y%m%d)/
cp -r ~/.cloudflared ~/backups/cloudflared-user-$(date +%Y%m%d)/

# Backup tunnel service
sudo cp /etc/systemd/system/cloudflared*.service ~/backups/

# Export tunnel logs
sudo journalctl -u cloudflared-evcc --since "7 days ago" --no-pager > ~/backups/cloudflared-logs-$(date +%Y%m%d).log
```

### Nginx Configuration

```bash
# Backup nginx configuration
sudo cp -r /etc/nginx/sites-available ~/backups/nginx-sites-$(date +%Y%m%d)/
sudo cp -r /etc/nginx/sites-enabled ~/backups/nginx-enabled-$(date +%Y%m%d)/
sudo cp /etc/nginx/nginx.conf ~/backups/nginx-main-$(date +%Y%m%d).conf
sudo cp /etc/nginx/.evcc_passwd ~/backups/nginx-passwords-$(date +%Y%m%d).txt

# Export nginx logs
sudo cp /var/log/nginx/access.log ~/backups/nginx-access-$(date +%Y%m%d).log
sudo cp /var/log/nginx/error.log ~/backups/nginx-error-$(date +%Y%m%d).log
```

### SSH Configuration

```bash
# Backup SSH config and keys
mkdir -p ~/backups/ssh-$(date +%Y%m%d)
cp ~/.ssh/config ~/backups/ssh-$(date +%Y%m%d)/
cp ~/.ssh/id_* ~/backups/ssh-$(date +%Y%m%d)/ 2>/dev/null
cp ~/.ssh/known_hosts* ~/backups/ssh-$(date +%Y%m%d)/ 2>/dev/null

# Backup system SSH config
sudo cp -r /etc/ssh ~/backups/ssh-system-$(date +%Y%m%d)/
```

### System Logs

```bash
# Configure journald for persistent logs
sudo mkdir -p /var/log/journal
sudo systemd-tmpfiles --create --prefix /var/log/journal
sudo systemctl restart systemd-journald

# Backup journald configuration
sudo cp /etc/systemd/journald.conf ~/backups/journald-$(date +%Y%m%d).conf

# Export all system logs
sudo journalctl --since "30 days ago" --no-pager > ~/backups/system-logs-$(date +%Y%m%d).log

# Export specific service logs
sudo journalctl -u evcc --since "30 days ago" --no-pager > ~/backups/evcc-full-logs-$(date +%Y%m%d).log
sudo journalctl -u nginx --since "30 days ago" --no-pager > ~/backups/nginx-system-logs-$(date +%Y%m%d).log
```

### Cron Jobs

```bash
# Backup all user cron jobs
crontab -l > ~/backups/user-crontab-$(date +%Y%m%d).txt

# Backup system cron jobs
sudo cp -r /etc/cron.d ~/backups/system-cron-$(date +%Y%m%d)/
sudo cp -r /etc/cron.daily ~/backups/cron-daily-$(date +%Y%m%d)/ 2>/dev/null
sudo cp -r /etc/cron.weekly ~/backups/cron-weekly-$(date +%Y%m%d)/ 2>/dev/null
sudo cp -r /etc/cron.monthly ~/backups/cron-monthly-$(date +%Y%m%d)/ 2>/dev/null
sudo cp /etc/crontab ~/backups/system-crontab-$(date +%Y%m%d).txt
```

### Network Configuration

```bash
# Backup network configuration
sudo cp /etc/dhcpcd.conf ~/backups/dhcpcd-$(date +%Y%m%d).conf
sudo cp -r /etc/netplan ~/backups/netplan-$(date +%Y%m%d)/ 2>/dev/null
sudo cp /etc/wpa_supplicant/wpa_supplicant.conf ~/backups/wifi-$(date +%Y%m%d).conf 2>/dev/null

# Export current network state
ip addr show > ~/backups/network-interfaces-$(date +%Y%m%d).txt
ip route show > ~/backups/network-routes-$(date +%Y%m%d).txt
cat /etc/resolv.conf > ~/backups/dns-config-$(date +%Y%m%d).txt
```

### Shell History

```bash
# Backup shell configuration and history
cp ~/.bashrc ~/backups/bashrc-$(date +%Y%m%d)
cp ~/.bash_history ~/backups/bash-history-$(date +%Y%m%d).txt
cp ~/.profile ~/backups/profile-$(date +%Y%m%d) 2>/dev/null
cp ~/.bash_aliases ~/backups/bash-aliases-$(date +%Y%m%d) 2>/dev/null

# Backup environment
env > ~/backups/environment-$(date +%Y%m%d).txt
```

### Systemd Services

```bash
# List enabled services
sudo systemctl list-enabled --no-pager > ~/backups/enabled-services-$(date +%Y%m%d).txt

# Backup custom service files
sudo cp /etc/systemd/system/evcc.service ~/backups/ 2>/dev/null
sudo cp /etc/systemd/system/cloudflared*.service ~/backups/ 2>/dev/null

# Export service status
sudo systemctl status evcc --no-pager > ~/backups/evcc-status-$(date +%Y%m%d).txt
sudo systemctl status nginx --no-pager > ~/backups/nginx-status-$(date +%Y%m%d).txt
sudo systemctl status cloudflared-evcc --no-pager > ~/backups/cloudflared-status-$(date +%Y%m%d).txt 2>/dev/null
```

## Restore Procedures

### EVCC Configuration Restore

```bash
# Restore EVCC config (with backup of existing files)
if [ -f /etc/evcc.yaml ]; then
    sudo cp /etc/evcc.yaml /etc/evcc.yaml.backup-$(date +%Y%m%d)
fi
sudo cp ~/backups/evcc-config-*/evcc.yaml /etc/evcc.yaml

# Restore service file
sudo cp ~/backups/evcc-config-*/evcc.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart evcc
```

### Battery Controller Restore

```bash
# Backup existing controller before restore
if [ -d ~/evcc-scripts ]; then
    cp -r ~/evcc-scripts ~/evcc-scripts.backup-$(date +%Y%m%d)
fi

# Restore battery controller
cp -r ~/backups/evcc-scripts-*/* ~/evcc-scripts/
crontab ~/backups/crontab-*.txt
```

### Cloudflare Tunnel Restore

```bash
# Backup existing tunnel config
if [ -d /etc/cloudflared ]; then
    sudo cp -r /etc/cloudflared /etc/cloudflared.backup-$(date +%Y%m%d)
fi

# Restore Cloudflare tunnel
sudo cp -r ~/backups/cloudflared-*/* /etc/cloudflared/
cp -r ~/backups/cloudflared-user-*/* ~/.cloudflared/
sudo cp ~/backups/cloudflared*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart cloudflared-evcc
```

### Nginx Restore

```bash
# Test nginx config before restore
sudo nginx -t

# Backup existing nginx config
sudo cp -r /etc/nginx /etc/nginx.backup-$(date +%Y%m%d)

# Restore nginx config
sudo cp -r ~/backups/nginx-sites-*/* /etc/nginx/sites-available/
sudo cp -r ~/backups/nginx-enabled-*/* /etc/nginx/sites-enabled/
sudo cp ~/backups/nginx-main-*.conf /etc/nginx/nginx.conf
sudo cp ~/backups/nginx-passwords-*.txt /etc/nginx/.evcc_passwd

# Test and restart
sudo nginx -t && sudo systemctl restart nginx
```

### SSH Configuration Restore

```bash
# Backup existing SSH config
if [ -d ~/.ssh ]; then
    cp -r ~/.ssh ~/.ssh.backup-$(date +%Y%m%d)
fi

# Restore SSH config
mkdir -p ~/.ssh
cp ~/backups/ssh-*/config ~/.ssh/ 2>/dev/null || true
cp ~/backups/ssh-*/id_* ~/.ssh/ 2>/dev/null || true
cp ~/backups/ssh-*/known_hosts* ~/.ssh/ 2>/dev/null || true

# Set correct permissions
chmod 700 ~/.ssh
chmod 600 ~/.ssh/id_* 2>/dev/null || true
chmod 600 ~/.ssh/config 2>/dev/null || true
chmod 644 ~/.ssh/known_hosts* 2>/dev/null || true
```

### Network Configuration Restore

```bash
# Restore network config
sudo cp ~/backups/dhcpcd-*.conf /etc/dhcpcd.conf
sudo cp ~/backups/wifi-*.conf /etc/wpa_supplicant/wpa_supplicant.conf 2>/dev/null
sudo systemctl restart dhcpcd
```

## Automated Backup Setup

### Daily Automated Backup

```bash
# Create automated backup script
cat > ~/evcc-daily-backup.sh << 'EOF'
#!/bin/bash
# Daily EVCC backup script

BACKUP_DIR="/home/kiechlus/backups/daily"
mkdir -p "$BACKUP_DIR"

# Keep only last 7 days of daily backups
find "$BACKUP_DIR" -name "evcc-daily-*.tar.gz" -mtime +7 -delete

# Run backup
~/evcc-backup.sh
mv ~/backups/evcc-*.tar.gz "$BACKUP_DIR/evcc-daily-$(date +%Y%m%d).tar.gz"
EOF

chmod +x ~/evcc-daily-backup.sh

# Add to cron for daily 2 AM backup
(crontab -l 2>/dev/null; echo "0 2 * * * /home/kiechlus/evcc-daily-backup.sh >> /var/log/evcc-backup.log 2>&1") | crontab -
```

### Weekly Full Backup

```bash
# Weekly comprehensive backup with log rotation
cat > ~/evcc-weekly-backup.sh << 'EOF'
#!/bin/bash
# Weekly comprehensive EVCC backup

BACKUP_DIR="/home/kiechlus/backups/weekly"
mkdir -p "$BACKUP_DIR"

# Keep only last 4 weeks of weekly backups
find "$BACKUP_DIR" -name "evcc-weekly-*.tar.gz" -mtime +28 -delete

# Full backup including logs and system state
~/evcc-backup.sh
mv ~/backups/evcc-*.tar.gz "$BACKUP_DIR/evcc-weekly-$(date +%Y%m%d).tar.gz"

# Log rotation for battery controller
sudo logrotate -f /etc/logrotate.d/evcc-battery-controller 2>/dev/null
EOF

chmod +x ~/evcc-weekly-backup.sh

# Add to cron for weekly Sunday 1 AM backup
(crontab -l 2>/dev/null; echo "0 1 * * 0 /home/kiechlus/evcc-weekly-backup.sh >> /var/log/evcc-backup.log 2>&1") | crontab -
```

### Remote Backup (Optional)

```bash
# Sync backups to remote location
cat > ~/evcc-remote-sync.sh << 'EOF'
#!/bin/bash
# Sync backups to remote server/cloud storage

REMOTE_HOST="backup-server.example.com"
REMOTE_PATH="/backups/raspberry-pi-evcc/"

# Sync to remote server via rsync
rsync -av --delete ~/backups/ user@$REMOTE_HOST:$REMOTE_PATH

# Or sync to cloud storage (example with rclone)
# rclone sync ~/backups/ cloud-storage:evcc-backups/
EOF

chmod +x ~/evcc-remote-sync.sh
```

## Backup Verification

```bash
# Verify backup integrity
~/verify-backup.sh() {
    BACKUP_FILE="$1"
    if [[ -f "$BACKUP_FILE" ]]; then
        echo "🔍 Verifying backup: $BACKUP_FILE"
        tar -tzf "$BACKUP_FILE" > /dev/null && echo "✅ Archive is valid" || echo "❌ Archive is corrupted"
        echo "📊 Backup size: $(du -sh "$BACKUP_FILE" | cut -f1)"
        echo "📅 Backup date: $(stat -c %y "$BACKUP_FILE")"
    else
        echo "❌ Backup file not found: $BACKUP_FILE"
    fi
}

# Usage
verify-backup ~/backups/evcc-*.tar.gz
```

This comprehensive backup and restore guide ensures you can recover your complete EVCC system including all configurations, logs, and customizations in case of hardware failure or system corruption.