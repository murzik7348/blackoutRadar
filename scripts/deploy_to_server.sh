#!/bin/bash
# Deploy Telegram Bot to Production Server
# Usage: ./deploy_to_server.sh <server_ip> <user@host>
# Example: ./deploy_to_server.sh 192.168.1.100 root@192.168.1.100

set -e

TARGET_USER="${1:-root}"
TARGET_HOST="${2:-root@localhost}"
TARGET_DIR="/root/telegram_bot"
REMOTE_CMD="ssh ${TARGET_HOST}"

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <user@host> [target_dir]"
    echo "Example: $0 root@192.168.1.100 /root/telegram_bot"
    exit 1
fi

TARGET_DIR="${2:-$TARGET_DIR}"

echo "🚀 DEPLOYING TELEGRAM BOT TO PRODUCTION SERVER"
echo "=================================================="
echo "Target: ${TARGET_HOST}"
echo "Directory: ${TARGET_DIR}"
echo ""

# Step 1: Create target directory
echo "1️⃣  Creating target directory..."
${REMOTE_CMD} "mkdir -p ${TARGET_DIR}"

# Step 2: Upload files
echo "2️⃣  Uploading files..."
scp -r telegram_bot/ ${TARGET_HOST}:${TARGET_DIR}/
scp telegram_bot_notification.service ${TARGET_HOST}:${TARGET_DIR}/
scp setup_production.sh ${TARGET_HOST}:${TARGET_DIR}/

# Step 3: Set permissions
echo "3️⃣  Setting permissions..."
${REMOTE_CMD} "chmod +x ${TARGET_DIR}/setup_production.sh"
${REMOTE_CMD} "chmod +x ${TARGET_DIR}/notification_service_simple.py"

# Step 4: Run setup
echo "4️⃣  Running production setup..."
${REMOTE_CMD} "cd ${TARGET_DIR} && bash setup_production.sh"

# Step 5: Verify deployment
echo ""
echo "5️⃣  Verifying deployment..."
${REMOTE_CMD} "systemctl status telegram_bot_notification --no-pager"

echo ""
echo "✅ DEPLOYMENT COMPLETE!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Verify logs: ssh ${TARGET_HOST} 'journalctl -u telegram_bot_notification -f'"
echo "2. Check status: ssh ${TARGET_HOST} 'systemctl status telegram_bot_notification'"
echo "3. View recent logs: ssh ${TARGET_HOST} 'journalctl -u telegram_bot_notification -n 20'"
