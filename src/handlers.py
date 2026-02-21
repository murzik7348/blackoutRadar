# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import json
import logging
from typing import List, Tuple
from .queues import QUEUES

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

# Исправленные импорты (вынесены из скобок telegram.ext)
from .parser import process_schedule_image
from .storage import set_user, get_user

ADMIN_ID = 6311296495

logger = logging.getLogger(__name__)

# Стейти
SELECT_REGION, CHOOSE_TYPE, SELECT_PLACE, ENTER_MANUAL, ASK_QUEUE_MAIN, ASK_QUEUE_SUB = range(6)

PAGE_SIZE = 10

# 24 області + АР Крим
REGIONS_LIST = [
    "Вінницька область",
    "Волинська область",
    "Дніпропетровська область",
    "Донецька область",
    "Житомирська область",
    "Закарпатська область",
    "Запорізька область",
    "Івано-Франківська область",
    "Київська область",
    "Кіровоградська область",
    "Луганська область",
    "Львівська область",
    "Миколаївська область",
    "Одеська область",
    "Полтавська область",
    "Рівненська область",
    "Сумська область",
    "Тернопільська область",
    "Харківська область",
    "Херсонська область",
    "Хмельницька область",
    "Черкаська область",
    "Чернівецька область",
    "Чернігівська область",
    "Автономна Республіка Крим",
]


def _load_zakarpattia() -> dict:
    """Завантажити список міст/сіл Закарпаття."""
    path = os.path.join(os.path.dirname(__file__), "..", "data", "zakarpattia_settlements.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _paginate(items: List[str], page: int, page_size: int = PAGE_SIZE) -> Tuple[List[str], int]:
    total = len(items)
    start = max(page, 0) * page_size
    end = start + page_size
    return items[start:end], total


def _region_keyboard(page: int) -> InlineKeyboardMarkup:
    slice_, total = _paginate(REGIONS_LIST, page)
    rows = [[InlineKeyboardButton(text=reg, callback_data=f"region|{reg}|{page}")] for reg in slice_]

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"regions_page|{page-1}"))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"regions_page|{page+1}"))
    if nav:
        rows.append(nav)

    return InlineKeyboardMarkup(rows)


def _type_keyboard(region: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🏙 Місто", callback_data=f"type|{region}|city"),
                InlineKeyboardButton("🏡 Село", callback_data=f"type|{region}|village"),
            ],
            [InlineKeyboardButton("🏳️ Змінити область", callback_data="restart_regions")],
        ]
    )


def _places_keyboard(context: ContextTypes.DEFAULT_TYPE, page: int) -> InlineKeyboardMarkup:
    """Клавіатура з містами/селами Закарпаття."""
    names: List[str] = context.user_data.get("places_list", [])
    place_type: str = context.user_data.get("place_type", "city")
    region: str = context.user_data.get("region", "Закарпатська область")

    slice_, total = _paginate(names, page)
    start_idx = page * PAGE_SIZE

    rows = []
    for offset, name in enumerate(slice_):
        idx = start_idx + offset
        rows.append(
            [InlineKeyboardButton(text=name, callback_data=f"place|{idx}")]
        )

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"places_page|{page-1}"))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"places_page|{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("🏳️ Змінити область", callback_data="restart_regions")])
    rows.append(
        [
            InlineKeyboardButton(
                "✏️ Ввести вручну",
                callback_data=f"manual|{region}|{place_type}",
            )
        ]
    )

    return InlineKeyboardMarkup(rows)


def _queue_main_keyboard() -> InlineKeyboardMarkup:
    # 1–6 черги
    buttons = [
        InlineKeyboardButton(str(i), callback_data=f"queue_main|{i}")
        for i in range(1, 7)
    ]

    # Розкладка 3 × 2
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]

    # Кнопка зміни локації
    rows.append([InlineKeyboardButton("🔁 Обрати іншу локацію", callback_data="restart_regions")])
    return InlineKeyboardMarkup(rows)


def _queue_sub_keyboard(main_q: str) -> InlineKeyboardMarkup:
    # автоматично формуємо підчерги
    subqueues = [f"{main_q}.1", f"{main_q}.2"]

    rows = [
        [InlineKeyboardButton(sub, callback_data=f"queue_sub|{sub}")]
        for sub in subqueues
    ]

    # кнопка назад
    rows.append([InlineKeyboardButton("⬅️ Назад (черга)", callback_data="back_to_main_queue")])

    return InlineKeyboardMarkup(rows)


async def restart_regions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Повертає до вибору області."""
    try:
        q = update.callback_query
        if q:
            await q.answer()
        
        page = context.user_data.get("regions_page", 0)
        kb = _region_keyboard(page)
        
        if q and q.message:
            await q.edit_message_text("Оберіть область зі списку:", reply_markup=kb)
        elif update.message:
            await update.message.reply_text("Оберіть область зі списку:", reply_markup=kb)
        elif update.effective_chat:
            await update.effective_chat.send_message("Оберіть область зі списку:", reply_markup=kb)
        
        return SELECT_REGION
    except Exception as e:
        logger.error(f"❌ Помилка в restart_regions: {e}", exc_info=True)
        try:
            if update.effective_chat:
                page = context.user_data.get("regions_page", 0)
                kb = _region_keyboard(page)
                await update.effective_chat.send_message("Оберіть область зі списку:", reply_markup=kb)
        except Exception as e2:
            logger.error(f"❌ Критична помилка при відправці повідомлення: {e2}", exc_info=True)
        return SELECT_REGION


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["regions_page"] = 0

    kb = _region_keyboard(page=0)

    if update.message:
        await update.message.reply_text(
            "Оберіть область зі списку:",
            reply_markup=kb,
        )
    else:
        await update.effective_chat.send_message(
            "Оберіть область зі списку:",
            reply_markup=kb,
        )

    return SELECT_REGION


async def on_regions_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, page_str = q.data.split("|")
    page = int(page_str)
    context.user_data["regions_page"] = page
    kb = _region_keyboard(page)
    await q.edit_message_reply_markup(reply_markup=kb)
    return SELECT_REGION


async def on_region_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, region, page_str = q.data.split("|")
    context.user_data["region"] = region
    
    # Перевіряємо, чи підтримується область
    if region != "Закарпатська область":
        message_text = (
            f"😔 На жаль, {region} ще немає в нашому боті.\n\n"
            f"Зачекайте трошки, згодом з'явиться! 🙏"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Повернутися до вибору області", callback_data="restart_regions")]
        ])
        
        await q.edit_message_text(
            message_text,
            reply_markup=keyboard
        )
        return SELECT_REGION
    
    # Якщо Закарпатська область - показуємо вибір типу
    await q.edit_message_text(
        f"Область: {region}\nОбери тип населеного пункту:",
        reply_markup=_type_keyboard(region),
    )
    return CHOOSE_TYPE


async def on_type_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, region, place_type = q.data.split("|")
    context.user_data["region"] = region
    context.user_data["place_type"] = place_type

    data = _load_zakarpattia()
    names = data["cities"] if place_type == "city" else data["villages"]
    names = sorted(names)

    context.user_data["places_list"] = names
    context.user_data["places_page"] = 0

    await q.edit_message_text(
        f"{'Міста' if place_type == 'city' else 'Села'} Закарпаття — "
        f"оберіть зі списку або натисніть «✏️ Ввести вручну»:",
        reply_markup=_places_keyboard(context, 0),
    )
    return SELECT_PLACE


async def on_places_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, page_str = q.data.split("|")
    page = int(page_str)
    context.user_data["places_page"] = page

    await q.edit_message_reply_markup(
        reply_markup=_places_keyboard(context, page)
    )
    return SELECT_PLACE


async def on_place_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, idx_str = q.data.split("|")
    idx = int(idx_str)

    names: List[str] = context.user_data.get("places_list", [])
    if 0 <= idx < len(names):
        name = names[idx]
    else:
        name = "Невідомо"

    region = context.user_data.get("region", "Закарпатська область")
    place_type = context.user_data.get("place_type", "city")

    set_user(update.effective_user.id, {"city": name, "region": region, "type": place_type})
    await q.edit_message_text(
        f"🏙 Місто/село: {name}\n🗺 Область: {region}\n\nОберіть чергу:",
        reply_markup=_queue_main_keyboard(),
    )
    return ASK_QUEUE_MAIN


async def on_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, region, place_type = q.data.split("|")
    context.user_data["region"] = region
    context.user_data["place_type"] = place_type
    await q.edit_message_text("Введіть назву населеного пункту текстом:")
    return ENTER_MANUAL


async def handle_manual_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = (update.message.text or "").strip()
    region = context.user_data.get("region", "Закарпатська область")
    place_type = context.user_data.get("place_type", "city")

    set_user(update.effective_user.id, {"city": name, "region": region, "type": place_type})
    await update.message.reply_text(
        f"🏙 Місто/село: {name}\n🗺 Область: {region}\n\nОберіть чергу:",
        reply_markup=_queue_main_keyboard(),
    )
    return ASK_QUEUE_MAIN


async def on_queue_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, main_q = q.data.split("|")
    context.user_data["queue_main"] = main_q
    await q.edit_message_text(
        f"Черга {main_q}. Оберіть підчергу:",
        reply_markup=_queue_sub_keyboard(main_q),
    )
    return ASK_QUEUE_SUB


async def back_to_main_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Оберіть чергу:", reply_markup=_queue_main_keyboard())
    return ASK_QUEUE_MAIN


async def on_queue_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    _, full_q = q.data.split("|")
    queue = full_q

    u = set_user(update.effective_user.id, {"queue": queue})
    await q.edit_message_text(
        f"✅ Дані збережено.\n"
        f"Місто/село: {u.get('city')} | Область: {u.get('region')} | Черга: {queue}\n"
        f"Ми надішлемо вам сповіщення за годину до відключення світла."
    )
    return ConversationHandler.END


async def handle_schedule_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка фотографії графіку (Тільки для адміна)."""
    user_id = update.effective_user.id
    
    # Перевірка: чи це адмін?
    if user_id != ADMIN_ID:
        return # Ігноруємо всіх інших

    status_msg = await update.message.reply_text("⏳ Бачу графік. Завантажую та обробляю...")

    try:
        # Качаємо фото
        photo = update.message.photo[-1]
        new_file = await photo.get_file()
        
        # Тимчасовий файл
        temp_file = "temp_schedule.jpg"
        await new_file.download_to_drive(temp_file)

        # Викликаємо парсер (він створить schedule.json)
        success, info = process_schedule_image(temp_file, 'schedule.json')

        # Видаляємо картинку
        if os.path.exists(temp_file):
            os.remove(temp_file)

        # Відповідаємо
        if success:
            await status_msg.edit_text(f"✅ {info}\n\nТепер дані оновлено для всіх користувачів.")
        else:
            await status_msg.edit_text(f"❌ {info}")

    except Exception as e:
        logger.error(f"Помилка при оновленні графіку: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Сталася помилка: {e}")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("Скасовано.")
    return ConversationHandler.END


def get_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_REGION: [
                CallbackQueryHandler(on_regions_page, pattern=r"^regions_page\|"),
                CallbackQueryHandler(on_region_chosen, pattern=r"^region\|"),
                CallbackQueryHandler(restart_regions, pattern=r"^restart_regions$"),
            ],
            CHOOSE_TYPE: [
                CallbackQueryHandler(on_type_chosen, pattern=r"^type\|"),
                CallbackQueryHandler(restart_regions, pattern=r"^restart_regions$"),
            ],
            SELECT_PLACE: [
                CallbackQueryHandler(on_places_page, pattern=r"^places_page\|"),
                CallbackQueryHandler(on_place_chosen, pattern=r"^place\|"),
                CallbackQueryHandler(restart_regions, pattern=r"^restart_regions$"),
                CallbackQueryHandler(on_manual, pattern=r"^manual\|"),
            ],
            ENTER_MANUAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manual_text),
                CallbackQueryHandler(restart_regions, pattern=r"^restart_regions$"),
            ],
            ASK_QUEUE_MAIN: [
                CallbackQueryHandler(on_queue_main, pattern=r"^queue_main\|"),
                CallbackQueryHandler(restart_regions, pattern=r"^restart_regions$"),
            ],
            ASK_QUEUE_SUB: [
                CallbackQueryHandler(on_queue_sub, pattern=r"^queue_sub\|"),
                CallbackQueryHandler(back_to_main_queue, pattern=r"^back_to_main_queue$"),
                CallbackQueryHandler(restart_regions, pattern=r"^restart_regions$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )


def get_handlers():
    return [
        # 1. Спочатку перевіряємо, чи скинув адмін фото
        MessageHandler(filters.PHOTO & filters.User(ADMIN_ID), handle_schedule_update),
        
        # 2. Потім запускаємо звичайну логіку (кнопки, меню)
        get_conversation_handler()
    ]