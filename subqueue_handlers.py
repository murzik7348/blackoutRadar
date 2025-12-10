from datetime import date
from typing import List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, Application
from .user_store import get_user, set_queue, set_subqueue
from .schedule_store import load_schedule

# Команди:
# /cherha  — вибір черги (1..10), потім вибір підчерги (динамічно з розкладу, або дефолт)
# /mysubqueue — показати поточні налаштування

MAX_QUEUES = 10

def _kb_queues() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for i in range(1, MAX_QUEUES+1):
        row.append(InlineKeyboardButton(str(i), callback_data=f"Q|{i}"))
        if len(row) == 5:
            rows.append(row); row = []
    if row: rows.append(row)
    return InlineKeyboardMarkup(rows)

def _kb_subqueues_for(queue_num: int, available: Optional[List[str]]) -> InlineKeyboardMarkup:
    buttons = []
    items = available if available else [f"{queue_num}-{i}" for i in range(1,7)]
    row = []
    for label in items:
        row.append(InlineKeyboardButton(label, callback_data=f"SUB|{label}"))
        if len(row) == 3:
            buttons.append(row); row = []
    if row: buttons.append(row)
    # додати “Без підчерги”
    buttons.append([InlineKeyboardButton("Без підчерги", callback_data="SUB|NONE")])
    return InlineKeyboardMarkup(buttons)

async def cmd_cherha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_chat.send_message(
        "Вибери свою чергу:",
        reply_markup=_kb_queues()
    )

async def on_queue_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data  # "Q|N"
    _, num = data.split("|", 1)
    queue_num = int(num)
    set_queue(update.effective_user.id, queue_num)
    # спробуємо запропонувати підчерги з розкладу на СЬОГОДНІ
    u = get_user(update.effective_user.id)
    city_id = u.get("city_id")
    avail = None
    if city_id:
        sched = load_schedule(city_id, date.today().isoformat())
        if sched and any("subqueue" in x for x in sched.get("queues", [])):
            # зібрати підчерги цієї черги
            s = sorted({x["subqueue"] for x in sched["queues"] if x.get("queue")==queue_num and "subqueue" in x})
            if s:
                avail = s
    await q.edit_message_text(
        f"Черга {queue_num}. Обери підчергу або пропусти:",
        reply_markup=_kb_subqueues_for(queue_num, avail)
    )

async def on_subqueue_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data  # "SUB|N-M" або "SUB|NONE"
    _, val = data.split("|", 1)
    if val == "NONE":
        set_subqueue(update.effective_user.id, None)
        await q.edit_message_text("Підчергу не вказано (будуть усі підчерги вибраної черги).")
    else:
        set_subqueue(update.effective_user.id, val)
        await q.edit_message_text(f"Підчерга збережена: {val}")

async def cmd_mysubqueue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    queue_num = u.get("queue")
    subq = u.get("subqueue")
    city = u.get("city"); oblast = u.get("oblast")
    txt = [
        f"Місто: {city or '—'} ({oblast or '—'})",
        f"Черга: {queue_num or '—'}",
        f"Підчерга: {subq or '—'}",
    ]
    await update.effective_chat.send_message("\n".join(txt))

def register_subqueue_handlers(app: Application) -> None:
    app.add_handler(CommandHandler(["cherha","queue"], cmd_cherha))
    app.add_handler(CallbackQueryHandler(on_queue_selected, pattern=r"^Q\|\d+$"))
    app.add_handler(CallbackQueryHandler(on_subqueue_selected, pattern=r"^SUB\|(.+)$"))
    app.add_handler(CommandHandler("mysubqueue", cmd_mysubqueue))
