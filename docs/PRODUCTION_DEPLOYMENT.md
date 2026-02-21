# 🚀 Telegram Bot Production Deployment Guide

## Quick Start

### 1. Local Testing (Development)
```bash
cd /path/to/telegram_bot
python3 notification_service_simple.py
```

### 2. Server Deployment (Production - Linux)

#### Prerequisites
- Ubuntu/Debian server
- Python 3.8+
- Root or sudo access

#### Installation Steps

```bash
# 1. Upload files to server
scp -r /path/to/telegram_bot/ root@your-server:/root/

# 2. SSH into server
ssh root@your-server

# 3. Run setup script
cd /root/telegram_bot
chmod +x setup_production.sh
sudo ./setup_production.sh

# 4. Verify service is running
sudo systemctl status telegram_bot_notification
```

#### Service Management

```bash
# View logs (real-time)
sudo journalctl -u telegram_bot_notification -f

# View last 50 lines
sudo journalctl -u telegram_bot_notification -n 50

# Stop service
sudo systemctl stop telegram_bot_notification

# Restart service
sudo systemctl restart telegram_bot_notification

# Check status
sudo systemctl status telegram_bot_notification

# View service file
cat /etc/systemd/system/telegram_bot_notification.service
```

## How It Works

1. **Service Start**: `telegram_bot_notification` service starts automatically on boot
2. **Notification Loop**: Checks every 60 seconds for notifications to send
3. **User Processing**: Processes all 8 users and their assigned queues
4. **Persistence**: Remembers sent notifications in `~/.telegram_bot_sent_notifications.json`
5. **Error Recovery**: Automatically restarts on failure (10-second delay)

## Key Features

✅ **Reliable**: Survives server restarts  
✅ **Scalable**: Handles all users and queues  
✅ **Persistent**: Tracks sent notifications across restarts  
✅ **Logged**: All events logged to systemd journal  
✅ **No Spam**: Deduplicates notifications  

## Troubleshooting

### Service won't start
```bash
sudo systemctl start telegram_bot_notification
sudo journalctl -u telegram_bot_notification -n 100
```

### Notifications not sending
```bash
# Check if service is running
sudo systemctl status telegram_bot_notification

# Check recent logs
sudo journalctl -u telegram_bot_notification -n 50 | grep ERROR

# Verify BOT_TOKEN is set
cat /root/telegram_bot/telegram_bot/config.py
```

### Reset sent notifications (force resend)
```bash
rm ~/.telegram_bot_sent_notifications.json
sudo systemctl restart telegram_bot_notification
```

## File Structure

```
telegram_bot/
├── notification_service_simple.py    # Main service script
├── telegram_bot_notification.service # Systemd service file
├── setup_production.sh               # Production setup script
├── telegram_bot/
│   ├── main.py                       # Core notification logic
│   ├── config.py                     # Configuration (BOT_TOKEN)
│   ├── storage.py                    # User data storage
│   ├── handlers.py                   # Telegram command handlers
│   └── ...
└── README.md                         # This file
```

## Configuration

### BOT_TOKEN
Set in `telegram_bot/config.py` or environment variable:
```bash
export BOT_TOKEN="your_token_here"
```

### Notification Schedule
Update `telegram_bot/schedule_YYYY-MM-DD.json` with your schedule:
```json
{
  "date": "2025-12-03",
  "timezone": "Europe/Kyiv",
  "schedule": {
    "1.1": [{"start": "02:53", "end": "02:54"}, ...],
    "5.1": [{"start": "00:59", "end": "01:00"}],
    ...
  }
}
```

### Users
Add/update users in `telegram_bot/user_data.json`:
```json
{
  "6311296495": {
    "queue": "5.1",
    "city": "Свалява",
    "region": "Закарпатська область"
  },
  ...
}
```

## Monitoring

### Check service health
```bash
sudo systemctl is-active telegram_bot_notification
```

### Get statistics
```bash
# Count total notifications sent today
sudo journalctl -u telegram_bot_notification --since today | grep "Всього надіслано" | tail -1

# Find errors
sudo journalctl -u telegram_bot_notification --since today | grep ERROR
```

## Performance

- **CPU**: Minimal (idle between checks)
- **Memory**: ~50MB
- **Network**: ~5KB per check + message bandwidth
- **Check Interval**: 60 seconds (configurable in `notification_service_simple.py`)

## Security Notes

⚠️ Ensure `config.py` has correct permissions:
```bash
chmod 600 /root/telegram_bot/telegram_bot/config.py
chmod 600 ~/.telegram_bot_sent_notifications.json
```

⚠️ Keep BOT_TOKEN secret - never commit to git

## Support

For issues or questions, check:
1. Service logs: `sudo journalctl -u telegram_bot_notification -f`
2. Application logs in `/root/telegram_bot/`
3. Verify BOT_TOKEN and schedule files exist
4. Ensure all users have `queue` field in `user_data.json`
