from __future__ import annotations

import asyncio
import os
import json
from datetime import datetime
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Kyiv")

USER_DATA_PATH = os.getenv("USER_DATA_PATH", "user_data.json")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

TARGET_QUEUE = "6.2"


def _load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _get_queue_key(user: Any) -> Optional[str]:
    if not isinstance(user, dict):
        return None

    q = user.get("queue")
    if isinstance(q, str) and q.strip():
        return q.strip()

    main = user.get("queue_main")
    sub = user.get("queue_sub")
    if isinstance(main, (int, str)) and isinstance(sub, (int, str)):
        return f"{main}.{sub}"

    return None


async def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN env var is not set")

    from telegram import Bot

    users: Dict[str, Any] = _load_json(USER_DATA_PATH, {})
    if not isinstance(users, dict) or not users:
        print("No users found")
        return

    bot = Bot(BOT_TOKEN)
    sent = 0

    for user_id_str, user in users.items():
        queue_key = _get_queue_key(user)
        if queue_key != TARGET_QUEUE:
            continue

        # chat_id беремо з user або з ключа
        chat_id_val = user.get("chat_id") if isinstance(user, dict) else None
        chat_id_val = chat_id_val or user_id_str

        try:
            chat_id = int(chat_id_val)
        except Exception:
            continue

        text = (
            "✅ Тестове сповіщення (лише черга 6.2).\n"
            f"Час: {datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')}"
        )

        try:
            await bot.send_message(chat_id=chat_id, text=text)
            sent += 1
        except Exception:
            continue

    print(f"Sent to {sent} users with queue {TARGET_QUEUE}")


if __name__ == "__main__":
    asyncio.run(main())

