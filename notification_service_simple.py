#!/usr/bin/env python3
"""Simplified notification sender that doesn't require full bot infrastructure."""
import asyncio
import time
import logging
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from telegram import Bot
from telegram_bot.config import BOT_TOKEN
import telegram_bot.main as main_module
from telegram_bot.main import notify_users

# Setup logging - minimal for production
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.WARNING  # Only show WARNING and above for production
)
logger = logging.getLogger(__name__)

# Persist sent notifications to file for reliability across restarts
SENT_NOTIFICATIONS_FILE = os.path.expanduser("~/.telegram_bot_sent_notifications.json")

def load_sent_notifications():
    """Load sent notifications from file."""
    if os.path.exists(SENT_NOTIFICATIONS_FILE):
        try:
            with open(SENT_NOTIFICATIONS_FILE, 'r') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_sent_notifications(notifications):
    """Save sent notifications to file."""
    try:
        with open(SENT_NOTIFICATIONS_FILE, 'w') as f:
            json.dump(list(notifications), f)
    except Exception as e:
        logger.error(f"Failed to save notifications: {e}")


async def notification_loop():
    """Run notification check every minute."""
    bot = Bot(token=BOT_TOKEN)
    
    # Load persisted notifications from previous runs
    main_module._SENT_NOTIFICATIONS = load_sent_notifications()
    
    logger.warning("🚀 NOTIFICATION SERVICE STARTED")
    logger.warning(f"📂 Loaded {len(main_module._SENT_NOTIFICATIONS)} persisted notifications")
    logger.warning("🔔🔔🔔 POST_INIT: JobQueue SERVICE RUNNING!")
    
    check_count = 0
    while True:
        try:
            check_count += 1
            logger.warning(f"🔔 CHECK #{check_count}: notify_users() running...")
            await notify_users(bot)
            
            # Persist notifications after each check
            save_sent_notifications(main_module._SENT_NOTIFICATIONS)
            
            logger.warning(f"🔔 CHECK #{check_count}: notify_users() completed! (Tracking {len(main_module._SENT_NOTIFICATIONS)} total notifications)")
            
            # Wait 60 seconds before next check
            for i in range(60):
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.warning("⏹️ Notification service stopped by user")
            break
        except Exception as e:
            logger.error(f"❌ Error in notification loop: {e}", exc_info=True)
            await asyncio.sleep(5)


async def main():
    """Main entry point."""
    try:
        if sys.platform == 'darwin':
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        await notification_loop()
    except Exception as e:
        logger.error(f"❌ Critical error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
