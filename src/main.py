from __future__ import annotations
import os
import json
import datetime
import asyncio
from typing import Optional

# 🔧 Хард-фікс для поламаного logging (твоя версія)
import logging as _logging

if not hasattr(_logging, "getLogger") or not callable(getattr(_logging, "getLogger", None)):
    class _DummyLogger:
        def debug(self, *args, **kwargs): pass
        def info(self, *args, **kwargs): pass
        def warning(self, *args, **kwargs): pass
        def error(self, *args, **kwargs): pass
        def exception(self, *args, **kwargs): pass
        def critical(self, *args, **kwargs): pass
        def log(self, *args, **kwargs): pass

    _dummy_logger = _DummyLogger()

    def getLogger(name: str | None = None):
        return _dummy_logger

    _logging.getLogger = getLogger

import logging
from telegram import Bot
from telegram.ext import ApplicationBuilder, ContextTypes
from telegram.constants import ParseMode
from telegram.error import NetworkError, TimedOut, Conflict

# Імпорти з твоїх файлів
from .storage import all_users
from .config import BOT_TOKEN
from .parser import process_schedule_image
# get_handlers імпортуємо всередині main, щоб уникнути циклічного імпорту

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Для сторонніх бібліотек
logging.getLogger('httpx').setLevel(logging.INFO)
logging.getLogger('httpcore').setLevel(logging.INFO)
logging.getLogger('telegram').setLevel(logging.INFO)
logging.getLogger('telegram.ext').setLevel(logging.INFO)
logging.getLogger('apscheduler').setLevel(logging.INFO)
logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
logging.getLogger('telegram.ext._updater').setLevel(logging.WARNING)

SCHEDULE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))


def load_schedule_for_date(date: Optional[datetime.date] = None):
    """Завантажує розклад для конкретної дати або поточної дати."""
    if date is None:
        date = datetime.date.today()
    
    date_str = date.strftime("%Y-%m-%d")
    schedule_file = os.path.join(SCHEDULE_DIR, f"schedule_{date_str}.json")
    
    if not os.path.exists(schedule_file):
        schedule_file = os.path.join(SCHEDULE_DIR, "schedule.json")
    
    if not os.path.exists(schedule_file):
        logger.warning(f"Розклад не знайдено для дати {date_str}")
        return {}
    
    try:
        with open(schedule_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("schedule", {})
    except Exception as e:
        logger.error(f"Помилка завантаження розкладу з {schedule_file}: {e}")
        return {}


async def notify_users(bot: Bot):
    """ТВОЯ повна логіка сповіщень."""
    now = datetime.datetime.now(datetime.timezone.utc).astimezone()
    current_date = now.date()
    current_time = now.strftime("%H:%M")

    if not hasattr(bot, '_sent_notifications'):
        bot._sent_notifications = set()
    
    today_str = current_date.strftime("%Y-%m-%d")
    bot._sent_notifications = {key for key in bot._sent_notifications if today_str in key}
    
    schedule = load_schedule_for_date(current_date)
    
    if not schedule:
        logger.warning(f"⚠️ Розклад порожній для дати {current_date}")
        return
    
    logger.info(f"📅 Завантажено розклад для {current_date}, черг: {len(schedule)}, поточний час: {current_time}")
    
    users = all_users()
    
    if not users:
        logger.warning("⚠️ Немає користувачів для перевірки")
        return
    
    logger.info(f"👥 Знайдено {len(users)} користувачів для перевірки")
    
    notified_count = 0
    
    for user_id, user in users.items():
        queue = user.get("queue")
        if not queue:
            continue

        notifications_enabled = user.get("notifications_enabled", True)
        if not notifications_enabled:
            continue

        intervals = schedule.get(queue, [])
        
        # Якщо черга без підчерги (наприклад "2"), перевіряємо обидві підчерги
        if not intervals and "." not in queue:
            queue_1 = f"{queue}.1"
            queue_2 = f"{queue}.2"
            intervals_1 = schedule.get(queue_1, [])
            intervals_2 = schedule.get(queue_2, [])
            intervals = intervals_1 + intervals_2
        
        if not intervals:
            continue
        
        for interval in intervals:
            start = interval["start"]
            end = interval.get("end", "")
            
            try:
                start_dt = datetime.datetime.strptime(start, "%H:%M").time()
                start_datetime = datetime.datetime.combine(current_date, start_dt)
                notify_datetime = start_datetime - datetime.timedelta(minutes=60)
                
                notify_time = notify_datetime.time().strftime("%H:%M")
                current_datetime = datetime.datetime.combine(current_date, now.time().replace(second=0, microsecond=0))
                
                if notify_datetime.date() < current_date:
                    time_to_start = (start_datetime - current_datetime).total_seconds() / 60
                    time_diff = None
                else:
                    time_diff = (current_datetime - notify_datetime).total_seconds() / 60
                    time_to_start = (start_datetime - current_datetime).total_seconds() / 60
                
                notification_key = f"{today_str}|{user_id}|{queue}|{start}|reminder"
                
                if time_diff is None:
                    should_notify = (0 < time_to_start <= 60)
                else:
                    should_notify = (
                        (-1 <= time_diff <= 1) or
                        (time_diff > 1 and 0 < time_to_start <= 60)
                    )
                
                if should_notify and notification_key not in bot._sent_notifications:
                    logger.info(f"✅ Час нагадування! Відправляю сповіщення користувачу {user_id}")
                    end_text = f" до *{end}*" if end else ""
                    text = (
                        f"⚠️ *Увага, буде відключення світла!* ⚡\n\n"
                        f"Ваша черга: *{queue}*\n"
                        f"Відключення о *{start}{end_text}*\n"
                        f"Це нагадування за *годину* до відключення."
                    )
                    
                    try:
                        await bot.send_message(
                            chat_id=int(user_id),
                            text=text,
                            parse_mode=ParseMode.MARKDOWN
                        )
                        bot._sent_notifications.add(notification_key)
                        notified_count += 1
                    except Exception as e:
                        logger.error(f"❌ Помилка надсилання сповіщення користувачу {user_id}: {e}")
                
                # Перевіряємо нагадування про включення світла
                if end:
                    try:
                        end_dt = datetime.datetime.strptime(end, "%H:%M").time()
                        
                        turn_on_notify_dt = (
                            datetime.datetime.combine(current_date, end_dt)
                            - datetime.timedelta(minutes=60)
                        ).time()
                        
                        turn_on_notify_datetime = datetime.datetime.combine(current_date, turn_on_notify_dt)
                        turn_on_time_diff = (current_datetime - turn_on_notify_datetime).total_seconds() / 60
                        
                        turn_on_reminder_key = f"{today_str}|{user_id}|{queue}|{end}|turn_on_reminder"
                        
                        if -1 <= turn_on_time_diff <= 1 and turn_on_reminder_key not in bot._sent_notifications:
                            logger.info(f"💡 Час нагадування про включення! Відправляю сповіщення користувачу {user_id}")
                            
                            text = (
                                f"💡 *Скоро включення світла!* ⚡\n\n"
                                f"Ваша черга: *{queue}*\n"
                                f"Відключення з *{start}* до *{end}*\n"
                                f"Світло буде включено о *{end}*\n"
                                f"Це нагадування за *годину* до включення."
                            )
                            
                            try:
                                await bot.send_message(
                                    chat_id=int(user_id),
                                    text=text,
                                    parse_mode=ParseMode.MARKDOWN
                                )
                                bot._sent_notifications.add(turn_on_reminder_key)
                                notified_count += 1
                            except Exception as e:
                                logger.error(f"❌ Помилка надсилання нагадування про включення користувачу {user_id}: {e}")
                        
                        end_datetime = datetime.datetime.combine(current_date, end_dt)
                        end_time_diff = (current_datetime - end_datetime).total_seconds() / 60
                        
                        turn_on_key = f"{today_str}|{user_id}|{queue}|{end}|turn_on"
                        
                        if -1 <= end_time_diff <= 1 and turn_on_key not in bot._sent_notifications:
                            logger.info(f"💡 Час включення! Відправляю сповіщення користувачу {user_id}")
                            
                            text = (
                                f"✅ *Світло включено!* 💡\n\n"
                                f"Ваша черга: *{queue}*\n"
                                f"Відключення було з *{start}* до *{end}*\n"
                                f"Світло вже працює! 🎉"
                            )
                            
                            try:
                                await bot.send_message(
                                    chat_id=int(user_id),
                                    text=text,
                                    parse_mode=ParseMode.MARKDOWN
                                )
                                bot._sent_notifications.add(turn_on_key)
                                notified_count += 1
                            except Exception as e:
                                logger.error(f"❌ Помилка надсилання сповіщення про включення користувачу {user_id}: {e}")
                    except ValueError as e:
                        logger.error(f"Помилка парсингу часу включення {end}: {e}")
            except ValueError as e:
                logger.error(f"Помилка парсингу часу {start}: {e}")
                continue
    
    if notified_count > 0:
        logger.info(f"✅ Всього надіслано {notified_count} сповіщень")


async def check_and_notify_job(context: ContextTypes.DEFAULT_TYPE):
    """Callback для scheduler - перевіряє і надсилає сповіщення."""
    bot = context.bot
    await notify_users(bot)


async def post_init(application):
    """Викликається після ініціалізації бота."""
    logger.info("✅ Бот запущено та готовий до роботи")
    if application.job_queue:
        application.job_queue.run_repeating(
            check_and_notify_job,
            interval=60,  # Кожну хвилину
            first=10,
            name="check_notifications"
        )


async def post_shutdown(application):
    """Викликається при завершенні роботи бота."""
    logger.info("Бот зупинено")


async def error_handler(update: object, context) -> None:
    """Обробка помилок."""
    error = context.error
    
    if isinstance(error, (NetworkError, TimedOut, Conflict)):
        logger.warning(f"⚠️ Telegram помилка: {error}")
        return
    
    logger.error(f"❌ Необроблена помилка: {error}", exc_info=True)


def main():
    """Головна функція для запуску бота."""
    from .handlers import get_handlers
    
    try:
        application = (
             ApplicationBuilder()
            .token(BOT_TOKEN)
            .post_init(post_init)
             .post_shutdown(post_shutdown)
                .build()
            )
        
        application.add_error_handler(error_handler)
        
        for handler in get_handlers():
            application.add_handler(handler)
        
        logger.info("🚀 Запуск бота...")
        application.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"❌ Критична помилка при запуску бота: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()