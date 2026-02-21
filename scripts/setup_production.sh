#!/bin/bash
# Production setup and start script for Telegram Bot Notification Service
# Usage: ./setup_production.sh

set -e

BOT_DIR="/root/telegram_bot"
SERVICE_NAME="telegram_bot_notification"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PYTHON_EXECUTABLE="/usr/bin/python3"

echo "🚀 TELEGRAM BOT NOTIFICATION SERVICE - PRODUCTION SETUP"
echo "=================================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use: sudo ./setup_production.sh)"
   exit 1
fi

# Step 1: Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install --no-cache-dir -q python-telegram-bot aiohttp

# Step 2: Setup systemd service
echo "🔧 Setting up systemd service..."
cp "$BOT_DIR/telegram_bot_notification.service" "$SERVICE_FILE"
sed -i "s|/root/telegram_bot|$BOT_DIR|g" "$SERVICE_FILE"

# Step 3: Reload systemd and enable service
echo "✅ Enabling service..."
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

# Step 4: Start the service
echo "🚀 Starting service..."
systemctl start "$SERVICE_NAME"

# Step 5: Check service status
echo ""
echo "📊 Service Status:"
systemctl status "$SERVICE_NAME" --no-pager

# Step 6: Show logs
echo ""
echo "📋 Recent Logs:"
journalctl -u "$SERVICE_NAME" -n 20 --no-pager

echo ""
echo "✅ PRODUCTION SETUP COMPLETE!"
echo "=================================================="
echo ""
echo "Commands:"
echo "  • View logs:     journalctl -u $SERVICE_NAME -f"
echo "  • Stop service:  sudo systemctl stop $SERVICE_NAME"
echo "  • Restart:       sudo systemctl restart $SERVICE_NAME"
echo "  • Status:        sudo systemctl status $SERVICE_NAME"
