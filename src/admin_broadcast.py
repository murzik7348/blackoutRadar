# telegram_bot/admin_broadcast.py
import os
import json
import argparse
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import Bot

KYIV_TZ = ZoneInfo("Europe/Kyiv")
HERE = Path(__file__).resolve().parent
DATA_FILE = HERE / ".." / "data" / "user_data.json"

def _get_token() -> str:
    t = os.getenv("BOT_TOKEN")
    if t and ":" in t:
        return t
    try:
        from telegram_bot.config_private import PRIVATE_TOKEN  # type: ignore
        if PRIVATE_TOKEN and ":" in PRIVATE_TOKEN:
            return PRIVATE_TOKEN
    except Exception:
        pass
    raise SystemExit("BOT_TOKEN відсутній. Задай env або telegram_bot/config_private.py")

def _load_users():
    if not DATA_FILE.exists():
        return {}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _pick_targets(users: dict, queues: set[int] | None):
    targets = []
    for uid_str, info in users.items():
        try:
            uid = int(uid_str)
        except Exception:
            continue
        q = str(info.get("queue") or "").strip()
        if not q:
            continue
        try:
            qn = int(q)
        except Exception:
            continue
        if queues is None or qn in queues:
            targets.append((uid, qn, info))
    return targets

def _build_text(city: str | None, queue: int, start_in: int, duration: int) -> str:
    now = datetime.now(KYIV_TZ)
    start = now + timedelta(minutes=start_in)
    end = start + timedelta(minutes=duration)
    when = f"{start.strftime('%Y-%m-%d %H:%M')}–{end.strftime('%H:%M')} Europe/Kyiv"
    return (
        "⚠️ ТЕСТОВЕ СПОВІЩЕННЯ\n"
        f"Місто: {city or 'не вказано'}\n"
        f"Черга: {queue}\n"
        f"Коли: {when}\n"
        "Це тест для перевірки сповіщень."
    )

async def _send_all(bot: Bot, targets, start_in: int, duration: int, text_override: str | None, dry: bool):
    sent = 0
    for uid, qn, info in targets:
        txt = text_override or _build_text(info.get("city"), qn, start_in, duration)
        if dry:
            print(f"[DRY] -> {uid}: {txt.replace('\n',' | ')}")
            continue
        try:
            await bot.send_message(chat_id=uid, text=txt, disable_web_page_preview=True)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            print(f"[ERR] uid={uid}: {e}")
    return sent

async def amain():
    ap = argparse.ArgumentParser(description="Адмін-розсилка тестових сповіщень по чергах")
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--all", action="store_true", help="Надіслати всім, у кого вибрана черга")
    grp.add_argument("--queue", "-q", type=str, help="Надіслати лише вказаним чергам, напр. '1' або '1,3,5'")
    ap.add_argument("--start-in", type=int, default=60, help="Початок через N хв (за замовч. 60)")
    ap.add_argument("--duration", type=int, default=90, help="Тривалість у хв (за замовч. 90)")
    ap.add_argument("--text", type=str, default=None, help="Свій текст (перекриває автогенерований)")
    ap.add_argument("--dry", action="store_true", help="Тільки показати, що буде надіслано")
    args = ap.parse_args()

    token = _get_token()
    users = _load_users()
    queues = None
    if args.queue:
        try:
            qs = [int(x.strip()) for x in args.queue.split(",") if x.strip()]
            queues = set(qs)
        except Exception:
            raise SystemExit("Невірний формат --queue. Приклад: -q 1,3,5")

    targets = _pick_targets(users, queues)
    if not targets:
        print("Немає користувачів з обраними чергами під умову.")
        return

    bot = Bot(token=token)
    total = await _send_all(bot, targets, args.start_in, args.duration, args.text, args.dry)
    if not args.dry:
        print(f"Готово. Надіслано: {total} повідомлень із {len(targets)} адресатів.")
    else:
        print(f"DRY-RUN. Адресатів: {len(targets)}")

if __name__ == "__main__":
    asyncio.run(amain())
