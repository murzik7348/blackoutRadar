import os
import json
import datetime
import asyncio
import logging
from typing import Optional
from telegram import Bot
from telegram.ext import ApplicationBuilder, ContextTypes
from telegram.constants import ParseMode
from telegram.error import NetworkError, TimedOut, Conflict

# Support both relative and direct imports
try:
    from .storage import all_users
    from .config import BOT_TOKEN
except ImportError:
    from telegram_bot.storage import all_users
    from telegram_bot.config import BOT_TOKEN

# Налаштування логування - показуємо ВСЕ для основного модуля
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    level=logging.DEBUG  # Показуємо все, включаючи DEBUG
)
logger = logging.getLogger(__name__)

# Для основного модуля показуємо все
logger.setLevel(logging.DEBUG)

# Для сторонніх бібліотек залишаємо INFO, щоб не засмічувати, але бачити важливе
logging.getLogger('httpx').setLevel(logging.INFO)
logging.getLogger('httpcore').setLevel(logging.INFO)
logging.getLogger('telegram').setLevel(logging.INFO)
logging.getLogger('telegram.ext').setLevel(logging.INFO)
logging.getLogger('apscheduler').setLevel(logging.INFO)
# Приховуємо тільки дуже шумні попередження
logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
logging.getLogger('telegram.ext._updater').setLevel(logging.WARNING)

SCHEDULE_DIR = os.path.dirname(__file__)

# Глобальне зберігання надісланих сповіщень (замість _SENT_NOTIFICATIONS)
_SENT_NOTIFICATIONS = set()


def load_schedule_for_date(date: Optional[datetime.date] = None):
    """Завантажує розклад для конкретної дати або поточної дати."""
    if date is None:
        date = datetime.date.today()
    
    # Формат: schedule_YYYY-MM-DD.json або schedule.json (за замовчуванням)
    date_str = date.strftime("%Y-%m-%d")
    schedule_file = os.path.join(SCHEDULE_DIR, f"schedule_{date_str}.json")
    
    # Якщо файл для конкретної дати не знайдено, використовуємо загальний
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
    """Перевіряє розклад і надсилає сповіщення користувачам за годину до відключення."""
    global _SENT_NOTIFICATIONS
    
    logger.warning("📢 notify_users() ЗАПУЩЕНА!")
    now = datetime.datetime.now(datetime.timezone.utc).astimezone()
    current_date = now.date()
    current_time = now.strftime("%H:%M")

    # Очищаємо старі записи (старіші за сьогодні)
    today_str = current_date.strftime("%Y-%m-%d")
    _SENT_NOTIFICATIONS = {key for key in _SENT_NOTIFICATIONS if today_str in key}
    
    # Завантажуємо розклад для поточної дати
    schedule = load_schedule_for_date(current_date)
    
    if not schedule:
        logger.warning(f"⚠️ Розклад порожній для дати {current_date}")
        return
    
    logger.info(f"📅 Завантажено розклад для {current_date}, черг: {len(schedule)}, поточний час: {current_time}")
    
    # Проходимо всіх користувачів
    users = all_users()
    logger.info(f"🔍 all_users() повернув: {type(users)}, кількість: {len(users) if isinstance(users, dict) else 'не словник'}")
    
    if not users:
        logger.warning("⚠️ Немає користувачів для перевірки")
        # Спробуємо завантажити напряму
        try:
            import json
            from .storage import DATA_PATH
            if os.path.exists(DATA_PATH):
                with open(DATA_PATH, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                logger.info(f"📂 Пряме читання файлу: ключі={list(raw_data.keys()) if isinstance(raw_data, dict) else 'не словник'}")
                if isinstance(raw_data, dict) and 'users' in raw_data:
                    users = raw_data['users']
                    logger.info(f"✅ Знайдено {len(users)} користувачів через пряме читання")
        except Exception as e:
            logger.error(f"❌ Помилка прямого читання: {e}")
    
    if not users:
        logger.warning("⚠️ Немає користувачів для перевірки")
        return
    
    logger.info(f"👥 Знайдено {len(users)} користувачів для перевірки")
    
    notified_count = 0
    
    for user_id, user in users.items():
        logger.info(f"🔍 Обробка користувача {user_id}: {user}")
        queue = user.get("queue")  # "1.1"
        if not queue:
            logger.info(f"⏭️ Користувач {user_id} не має черги (user={user})")
            continue

        # Перевіряємо, чи увімкнені сповіщення (за замовчуванням - так)
        notifications_enabled = user.get("notifications_enabled", True)
        if not notifications_enabled:
            logger.info(f"⏭️ Сповіщення вимкнені для користувача {user_id}")
            continue

        logger.info(f"🔎 Перевіряю користувача {user_id}, черга: {queue}")
        
        # Беремо таймінги саме для цієї черги
        # Підтримуємо обидва формати: "2" та "2.1"
        intervals = schedule.get(queue, [])
        logger.info(f"📋 Черга {queue}: знайдено {len(intervals)} інтервалів безпосередньо в розкладі")
        
        # Якщо черга без підчерги (наприклад "2"), перевіряємо обидві підчерги ("2.1" та "2.2")
        if not intervals and "." not in queue:
            queue_1 = f"{queue}.1"
            queue_2 = f"{queue}.2"
            intervals_1 = schedule.get(queue_1, [])
            intervals_2 = schedule.get(queue_2, [])
            intervals = intervals_1 + intervals_2
            logger.info(f"🔗 Черга {queue} без підчерги, об'єднано {queue_1} ({len(intervals_1)} інт.) та {queue_2} ({len(intervals_2)} інт.): всього {len(intervals)} інтервалів")
        
        if not intervals:
            # Черга існує в розкладі, але має порожній масив інтервалів - сьогодні немає відключень для цієї черги
            logger.info(f"ℹ️ Для черги {queue} користувача {user_id} сьогодні немає відключень (порожній масив інтервалів)")
            continue
        
        logger.info(f"👤 Користувач {user_id}, черга {queue}, інтервалів: {len(intervals)}")
        
        for interval in intervals:
            start = interval.get("start")   # "09:00" -使用 .get() для безпеки
            end = interval.get("end", "")
            
            # Пропускаємо інтервали без часу початку
            if not start:
                logger.warning(f"⚠️ Інтервал без часу початку для черги {queue}: {interval}")
                continue
            
            try:
                start_dt = datetime.datetime.strptime(start, "%H:%M").time()

                # Віднімаємо 60 хвилин (годину) для нагадування
                start_datetime = datetime.datetime.combine(current_date, start_dt)
                notify_datetime = start_datetime - datetime.timedelta(minutes=60)
                
                notify_time = notify_datetime.time().strftime("%H:%M")
                current_datetime = datetime.datetime.combine(current_date, now.time().replace(second=0, microsecond=0))
                
                # Якщо час нагадування вийшов на попередній день, корегуємо дату для правильного порівняння
                if notify_datetime.date() < current_date:
                    # Час нагадування був вчора - це означає, що час нагадування вже пройшов
                    # Перевіряємо тільки, чи відключення ще не настало
                    time_to_start = (start_datetime - current_datetime).total_seconds() / 60
                    time_diff = None  # Не використовуємо для випадку переходу через північ
                else:
                    # Час нагадування сьогодні - нормальне порівняння
                    time_diff = (current_datetime - notify_datetime).total_seconds() / 60  # різниця в хвилинах
                    time_to_start = (start_datetime - current_datetime).total_seconds() / 60  # скільки хвилин до відключення
                
                logger.info(f"🔍 Перевірка: користувач {user_id}, черга {queue}, відключення {start}, нагадування {notify_time}, поточний час {current_time}, різниця: {time_diff:.1f} хв, до відключення: {time_to_start:.1f} хв" if time_diff is not None else f"🔍 Перевірка: користувач {user_id}, черга {queue}, відключення {start}, нагадування {notify_time} (вчора), поточний час {current_time}, до відключення: {time_to_start:.1f} хв")
                
                # Унікальний ключ для сповіщення (використовуємо дату та час події, а не поточний час)
                notification_key = f"{today_str}|{user_id}|{queue}|{start}|reminder"
                
                # Перевіряємо — зараз час нагадування? (дозволяємо ±1 хвилину) АБО час нагадування вже пройшов, але відключення ще не настало
                # Надсилаємо сповіщення, якщо:
                # 1. Поточний час в межах ±1 хвилини від часу нагадування (якщо час нагадування сьогодні)
                # 2. АБО час нагадування вже пройшов (вчора або сьогодні), але відключення ще не закінчилось (time_to_start може бути від -60 до 60)
                if time_diff is None:
                    # Час нагадування був вчора - надсилаємо, якщо відключення ще не закінчилось
                    # time_to_start < 0 означає, що це вже під час відключення
                    # time_to_start > 0 означає, що відключення ще не почалось
                    should_notify = (-60 < time_to_start <= 60)
                else:
                    # Час нагадування сьогодні
                    should_notify = (
                        (-1 <= time_diff <= 1) or  # Точний час нагадування
                        (time_diff > 1 and -60 < time_to_start <= 60)  # Час нагадування пройшов, але відключення ще в межах часового вікна
                    )
                
                if should_notify and notification_key not in _SENT_NOTIFICATIONS:
                    logger.warning(f"✅✅✅ ЧАС НАГАДУВАННЯ! Користувач {user_id}, черга {queue}, відключення {start}, нагадування {notify_time}, поточний час {current_time}")
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
                        _SENT_NOTIFICATIONS.add(notification_key)
                        notified_count += 1
                        logger.info(f"✅ Надіслано сповіщення про відключення користувачу {user_id} для черги {queue} о {start}")
                    except Exception as e:
                        logger.error(f"❌ Помилка надсилання сповіщення користувачу {user_id}: {e}")
                
                # Перевіряємо нагадування про включення світла (якщо є час end)
                if end:
                    try:
                        end_dt = datetime.datetime.strptime(end, "%H:%M").time()
                        end_datetime = datetime.datetime.combine(current_date, end_dt)
                        
                        # Віднімаємо 60 хвилин (годину) для нагадування про включення
                        turn_on_notify_datetime = end_datetime - datetime.timedelta(minutes=60)
                        turn_on_notify_time = turn_on_notify_datetime.time().strftime("%H:%M")
                        
                        # Перевіримо логіку для нагадування про включення (аналогічно як для відключення)
                        if turn_on_notify_datetime.date() < current_date:
                            # Час нагадування про включення був вчора - перевіряємо, чи включення ще не завершилось
                            turn_on_time_to_end = (end_datetime - current_datetime).total_seconds() / 60
                            turn_on_time_diff = None
                            should_notify_turn_on = (-60 < turn_on_time_to_end <= 60)
                        else:
                            # Час нагадування про включення сьогодні
                            turn_on_time_diff = (current_datetime - turn_on_notify_datetime).total_seconds() / 60
                            turn_on_time_to_end = (end_datetime - current_datetime).total_seconds() / 60
                            should_notify_turn_on = (
                                (-1 <= turn_on_time_diff <= 1) or
                                (turn_on_time_diff > 1 and -60 < turn_on_time_to_end <= 60)
                            )
                        
                        logger.info(f"🔍 Перевірка нагадування про включення: користувач {user_id}, черга {queue}, включення {end}, нагадування {turn_on_notify_time}, поточний час {current_time}, різниця: {turn_on_time_diff if turn_on_time_diff is not None else 'вчора'}")
                        
                        # Унікальний ключ для сповіщення про включення (використовуємо дату та час події)
                        turn_on_reminder_key = f"{today_str}|{user_id}|{queue}|{end}|turn_on_reminder"
                        
                        # Перевіряємо — зараз час нагадування про включення? І чи не надсилали вже
                        if should_notify_turn_on and turn_on_reminder_key not in _SENT_NOTIFICATIONS:
                            logger.warning(f"💡💡💡 ЧАС НАГАДУВАННЯ ПРО ВКЛЮЧЕННЯ! Користувач {user_id}, черга {queue}, включення {end}, нагадування {turn_on_notify_time}, поточний час {current_time}")
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
                                _SENT_NOTIFICATIONS.add(turn_on_reminder_key)
                                notified_count += 1
                                logger.info(f"✅ Надіслано нагадування про включення користувачу {user_id} для черги {queue} о {end}")
                            except Exception as e:
                                logger.error(f"❌ Помилка надсилання нагадування про включення користувачу {user_id}: {e}")
                        
                        # Перевіряємо включення світла (в момент включення)
                        # Переконаємось, що end_datetime був уже розраховане вище
                        end_time_diff = (current_datetime - end_datetime).total_seconds() / 60  # різниця в хвилинах
                        
                        logger.info(f"🔍 Перевірка включення: користувач {user_id}, черга {queue}, включення {end}, поточний час {current_time}, різниця: {end_time_diff:.1f} хв")
                        
                        # Унікальний ключ для сповіщення про включення (використовуємо дату та час події)
                        turn_on_key = f"{today_str}|{user_id}|{queue}|{end}|turn_on"
                        
                        # Перевіряємо — зараз час включення? (дозволяємо ±1 хвилину) І чи не надсилали вже
                        # Розширюємо логіку, щоб охопити випадки, коли час включення був на попередній день
                        if end_datetime.date() < current_date:
                            # Час включення був вчора - не надсилаємо (вже минуло, не слід спамити)
                            should_notify_turn_on_final = False
                        else:
                            # Час включення сьогодні - перевіряємо точний час
                            should_notify_turn_on_final = (-1 <= end_time_diff <= 1)
                        
                        if should_notify_turn_on_final and turn_on_key not in _SENT_NOTIFICATIONS:
                            logger.warning(f"💡💡💡 ЧАС ВКЛЮЧЕННЯ! Користувач {user_id}, черга {queue}, включення {end}, поточний час {current_time}")
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
                                _SENT_NOTIFICATIONS.add(turn_on_key)
                                notified_count += 1
                                logger.info(f"✅ Надіслано сповіщення про включення користувачу {user_id} для черги {queue} о {end}")
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
    logger.warning("🔔 check_and_notify_job ЗАПУЩЕНА!")
    bot = context.bot
    await notify_users(bot)
    logger.warning("🔔 check_and_notify_job ЗАВЕРШЕНА!")


async def post_init(application):
    """Викликається після ініціалізації бота."""
    logger.warning("🚀🚀🚀 POST_INIT ЗАПУЩЕНО! Ініціалізація JobQueue...")
    # Використовуємо вбудований JobQueue для перевірки кожну хвилину
    if application.job_queue:
        logger.warning("✅ JobQueue ЗНАЙДЕНА! Запускаю check_notifications кожні 60 сек...")
        application.job_queue.run_repeating(
            check_and_notify_job,
            interval=60,  # Кожну хвилину (60 секунд)
            first=3,  # Почати через 3 секунди після запуску (було 10)
            name="check_notifications"
        )
        logger.warning("✅ Перша перевірка запуститься за 3 сек")
    else:
        logger.error("❌❌❌ КРИТИЧНА ПОМИЛКА: JobQueue НЕ ЗНАЙДЕНА!")


async def post_shutdown(application):
    """Викликається при завершенні роботи бота."""
    scheduler = application.bot_data.get('scheduler')
    if scheduler:
        scheduler.shutdown()
        logger.info("Scheduler зупинено")
    logger.info("Бот зупинено")


async def error_handler(update: object, context) -> None:
    """Обробка помилок."""
    error = context.error
    error_type = type(error).__name__
    
    # Перевіряємо тип помилки перед обробкою
    if isinstance(error, (NetworkError, TimedOut)):
        # Мережеві помилки - показуємо, але без повного traceback
        logger.warning(f"⚠️ Мережева помилка або таймаут: {error}")
        return
    elif isinstance(error, Conflict):
        # Conflict - кілька екземплярів бота запущено одночасно - просто ігноруємо
        logger.debug(f"⚠️ Conflict: інший екземпляр бота запущено (це нормально, якщо перезапускаєте бота)")
        return
    elif "Conflict" in error_type or "conflict" in str(error).lower():
        # Додаткова перевірка на випадок, якщо тип помилки не визначено правильно
        logger.debug(f"⚠️ Conflict (виявлено за текстом): інший екземпляр бота запущено")
        return
    
    # Всі інші помилки логуємо з повним traceback
    logger.error(f"❌ Необроблена помилка: {error}", exc_info=True)


def main():
    """Головна функція для запуску бота."""
    try:
        from .handlers import get_handlers
    except ImportError:
        from telegram_bot.handlers import get_handlers
    
    try:
        # На macOS створюємо event loop перед інною ініціалізацією
        import sys
        if sys.platform == "darwin":
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        else:
            loop = None
        
        # Створюємо додаток (використовуємо вбудований JobQueue)
        application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
        
        # Додаємо обробник помилок
        application.add_error_handler(error_handler)
        
        # Додаємо обробники команд
        for handler in get_handlers():
            application.add_handler(handler)
        
        # Запускаємо бота
        logger.info("🚀 Запуск бота...")
        application.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"❌ Критична помилка при запуску бота: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
