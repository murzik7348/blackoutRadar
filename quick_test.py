#!/usr/bin/env python3
"""Quick test of notify_users with current schedule."""

import asyncio
import sys
import os
import json
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from telegram_bot.main import notify_users
from telegram import Bot
from telegram_bot.config import BOT_TOKEN


class MockBot:
    """Mock Bot for testing without Telegram connection."""
    
    def __init__(self):
        self._sent_notifications = set()
        self.sent_messages = []
    
    async def send_message(self, chat_id, text, parse_mode=None):
        """Mock message sending."""
        self.sent_messages.append({
            'chat_id': chat_id,
            'text': text,
            'time': datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S")
        })
        print(f"📨 [{datetime.now().strftime('%H:%M:%S')}] Повідомлення користувачу {chat_id}")


async def main():
    """Test notification logic."""
    print("=" * 80)
    print("🔍 ТЕСТ ФУНКЦІЇ notify_users()")
    print("=" * 80)
    print()
    
    # Show current schedule
    today_file = os.path.join(os.path.dirname(__file__), 'telegram_bot', 'schedule_2025-12-03.json')
    if os.path.exists(today_file):
        with open(today_file) as f:
            schedule = json.load(f)
        print(f"📅 Розклад: {schedule['date']}")
        print(f"🕐 Поточний час: {datetime.now(timezone.utc).astimezone().strftime('%H:%M:%S')}")
        print()
        
        # Show 5.1 queue
        queue_5_1 = schedule['schedule'].get('5.1', [])
        if queue_5_1:
            print(f"🎯 Черга 5.1: {queue_5_1}")
        print()
    
    bot = MockBot()
    await notify_users(bot)
    
    print()
    print("=" * 80)
    if bot.sent_messages:
        print(f"✅ РЕЗУЛЬТАТ: Надіслано {len(bot.sent_messages)} сповіщень")
        for i, msg in enumerate(bot.sent_messages, 1):
            print(f"   {i}. User {msg['chat_id']} ({msg['time']})")
    else:
        print("❌ РЕЗУЛЬТАТ: Жодних сповіщень не надіслано")
    print("=" * 80)
    
    return len(bot.sent_messages)


if __name__ == "__main__":
    count = asyncio.run(main())
    sys.exit(0 if count > 0 else 1)
