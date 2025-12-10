#!/bin/bash
set -e

SERVER="dima@192.168.0.177"
DEST="/home/dima/telegram_bot"

echo "=== SYNC CODE ==="
rsync -av --delete \
  --exclude=".git" \
  --exclude=".venv" \
  --exclude="logs" \
  ./ "$SERVER:$DEST/"

echo "=== RESTART SERVICE ==="
ssh "$SERVER" 'sudo systemctl restart telegram_bot.service && sudo systemctl status telegram_bot.service --no-pager'

