import json
import datetime
import asyncio
from telegram import Bot
from telegram.constants import ParseMode

SCHEDULE_FILE = os.path.join(os.path.dirname(__file__), "schedule.json")


def load_schedule():
    with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["schedule"]


async def notify_users(bot: Bot):
    schedule = load_schedule()
    now = datetime.datetime.now(datetime.timezone.utc).astimezone()

    current_time = now.strftime("%H:%M")

    # проходимо всі черги 1.1, 1.2 ... 6.2
    for user_id, user in get_user().items():
        queue = user.get("queue")  # "1.1"
        if not queue:
            continue

        # беремо таймінги саме для цієї черги
        intervals = schedule.get(queue, [])
        for interval in intervals:
            start = interval["start"]   # "09:00"
            start_dt = datetime.datetime.strptime(start, "%H:%M").time()

            # віднімаємо 10 хвилин (було 15)
            notify_dt = (datetime.datetime.combine(now.date(), start_dt)
                         - datetime.timedelta(minutes=10)).time()

            notify_time = notify_dt.strftime("%H:%M")

            # перевіряємо — зараз час нагадування?
            if current_time == notify_time:
                text = (
                    f"⚠️ *Увага!* Буде відключення світла ⚡\n\n"
                    f"Черга: *{queue}*\n"
                    f"Початок о *{start}*\n"
                    f"Нагадуємо за *10 хвилин*."
                )

                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass

