
import os
from dotenv import load_dotenv
load_dotenv()

# Спробуємо отримати токен з різних джерел
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Якщо не знайдено, спробуємо з config_private.py
if not BOT_TOKEN:
    try:
        from .config_private import PRIVATE_TOKEN
        BOT_TOKEN = PRIVATE_TOKEN
    except ImportError:
        pass

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не заданий. Додай у .env або зроби export BOT_TOKEN=...")

POLL_DROP_PENDING = True
