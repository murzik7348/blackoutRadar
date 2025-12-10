# telegram_bot/handlers.py
from __future__ import annotations

import json
import os
from typing import Dict, Any

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import aiohttp

# Шлях до нашого JSON
USER_DATA_PATH = os.path.join(os.path.dirname(__file__), "user_data.json")

# СТАНИ для ConversationHandler (тільки під локацію)
ASK_LOCATION = 1

# ------- Черги: дефолт і переозначення по містах -------
DEFAULT_QUEUE_COUNT = 5
QUEUE_COUNT_BY_CITY = {
    "Київ": 6,
    "Львів": 5,
}

def get_queue_count(city: str | None) -> int:
    return int(QUEUE_COUNT_BY_CITY.get((city or "").strip(), DEFAULT_QUEUE_COUNT))

def build_queue_keyboard(n: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for i in range(1, n + 1):
        row.append(InlineKeyboardButton(f"Черга {i}", callback_data=f"QUEUE_{i}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)

# ------- Reverse geocode міста за координатами -------
async def reverse_geocode_city(lat: float, lon: float) -> tuple[str|None, str|None]:
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {"lat": lat, "lon": lon, "format": "json", "zoom": 10, "addressdetails": 1}
    headers = {"User-Agent": "dtek-outage-bot/1.0"}
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as s:
        async with s.get(url, params=params, headers=headers) as r:
            data = await r.json(content_type=None)
    address = data.get("address", {}) if isinstance(data, dict) else {}
    city = address.get("city") or address.get("town") or address.get("village") or address.get("municipality")
    oblast = address.get("state") or address.get("region")
    return city, oblast



# ---------- УТИЛІТИ ----------

def _load_users() -> Dict[str, Any]:
    try:
        with open(USER_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save_users(data: Dict[str, Any]) -> None:
    with open(USER_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _ensure_user_entry(user_id: int) -> Dict[str, Any]:
    data = _load_users()
    key = str(user_id)
    if key not in data or not isinstance(data[key], dict):
        data[key] = {}
    return data

# ---------- ХЕНДЛЕРИ КОМАНД ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Привіт! Я бот сповіщень про відключення світла ⚡️\n"
        "Натисни /register, щоб пройти просту реєстрацію (геолокація + черга)."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Доступні команди:\n"
        "/register — реєстрація (локація + черга)\n"
        "/help — допомога"
    )

# ---------- РЕЄСТРАЦІЯ: КРОК 1 — ЛОКАЦІЯ ----------

async def register_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Просимо геолокацію через системну клавіатуру
    kb = [[KeyboardButton(text="📍 Надіслати геолокацію", request_location=True)]]
    await update.effective_message.reply_text(
        "Надішли, будь ласка, геолокацію (кнопкою нижче).",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True),
    )
    return ASK_LOCATION

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.location:
        await update.effective_message.reply_text(
            "Не бачу локації. Спробуй ще раз: /register"
        )
        return ConversationHandler.END

    lat = update.message.location.latitude
    lon = update.message.location.longitude
    uid = update.effective_user.id

    data = _ensure_user_entry(uid)
    data[str(uid)]["latitude"] = float(lat)
    data[str(uid)]["longitude"] = float(lon)

    city, oblast = await reverse_geocode_city(lat, lon)
    if city:
        data[str(uid)]["city"] = city
    if oblast:
        data[str(uid)]["region"] = oblast
    _save_users(data)

    # Прибрали клавіатуру та показуємо вибір черги
    await update.effective_message.reply_text(
        "Дякую! Тепер обери свою чергу.",
        reply_markup=ReplyKeyboardRemove(),
    )

    keyboard = [
        [
            InlineKeyboardButton("Черга 1", callback_data="QUEUE_1"),
            InlineKeyboardButton("Черга 2", callback_data="QUEUE_2"),
            InlineKeyboardButton("Черга 3", callback_data="QUEUE_3"),
        ]
    ]
    await update.effective_message.reply_text(
        "Вибери чергу:", reply_markup=InlineKeyboardMarkup(keyboard)
    )

    # Розв'язуємо Conversation тут — далі працює глобальний CallbackQueryHandler
    return ConversationHandler.END

# ---------- ВИБІР ЧЕРГИ (INLINE КНОПКИ) ----------

async def queue_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробка натискання інлайн-кнопок 'QUEUE_1/2/3'."""
    query = update.callback_query
    if not query:
        return

    await query.answer()

    uid = update.effective_user.id
    data = _ensure_user_entry(uid)

    payload = query.data or ""
    if payload.startswith("QUEUE_"):
        queue = payload.replace("QUEUE_", "").strip()
        if not queue.isdigit():
            await query.edit_message_text("Некоректна черга. Спробуй ще раз: /register")
            return
        max_q = int(data[str(uid)].get('queue_max', DEFAULT_QUEUE_COUNT))
        qn = int(queue)
        if not (1 <= qn <= max_q):
            await query.edit_message_text(f"Некоректна черга. Оберіть 1–{max_q} або /register")
            return

        data[str(uid)]["queue"] = queue
        _save_users(data)

        await query.edit_message_text(
            f"✅ Готово! Збережено: черга {queue}.\n"
            f"Тепер я зможу надсилати попередження згідно з розкладом."
        )

# ---------- РЕЄСТРАЦІЯ ХЕНДЛЕРІВ ----------

def register_handlers(application: Application) -> None:
    # Команди
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))

    # Conversation тільки для локації (без callback'ів всередині)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("register", register_cmd)],
        states={
            ASK_LOCATION: [MessageHandler(filters.LOCATION, handle_location)],
        },
        fallbacks=[],
        # БЕЗ per_message параметра — щоб не було попереджень
    )
    application.add_handler(conv_handler)

    # CallbackQueryHandler — окремо, глобально
    application.add_handler(CallbackQueryHandler(queue_chosen, pattern=r"^QUEUE_\d+$"))
