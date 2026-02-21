"""
AUTO REPAIR SCRIPT — Telegram Bot Fixer
Author: Codex Assistant
Purpose: Automatically detect and fix version conflicts in Telegram bot projects.
"""

import importlib.metadata
import os
import re
import sys

BOT_FOLDER = "telegram_bot"

# Detect python version
PY_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"

# Detect installed telegram library version
try:
    PTB_VERSION = importlib.metadata.version("python-telegram-bot")
except importlib.metadata.PackageNotFoundError:
    PTB_VERSION = None

print(f"Detected Python: {PY_VERSION}")
print(f"Detected python-telegram-bot: {PTB_VERSION}")

# Determine which syntax to use
USE_NEW_API = False
if PTB_VERSION:
    major = int(PTB_VERSION.split(".")[0])
    if major >= 20:
        USE_NEW_API = True

# Function to rewrite imports and structure
def rewrite_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        code = f.read()

    if not USE_NEW_API:
        # Legacy Updater API (for v13.x)
        code = re.sub(r"from\s+telegram\.constants\s+import\s+ParseMode", "from telegram import ParseMode", code)
        code = re.sub(r"from\s+telegram\.ext\s+import\s+Application.*", "from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, ConversationHandler", code)
        code = code.replace("ApplicationBuilder", "Updater")
        code = re.sub(r"application\.run_polling\(\)", "updater.start_polling()", code)
        code = re.sub(r"application\.add_handler", "updater.dispatcher.add_handler", code)
        code = re.sub(r"application\s*=\s*.*", "updater = Updater(token=BOT_TOKEN, use_context=True)", code)
        print(f"✅ Converted to Updater API: {file_path}")
    else:
        # Application API (for v20+)
        code = re.sub(r"from\s+telegram\.ext\s+import\s+.*", "from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler", code)
        code = re.sub(r"Updater", "ApplicationBuilder", code)
        code = re.sub(r"Filters", "filters", code)
        print(f"✅ Converted to Application API: {file_path}")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(code)

# Walk through the bot folder and rewrite .py files
for root, _, files in os.walk(BOT_FOLDER):
    for file in files:
        if file.endswith(".py"):
            rewrite_file(os.path.join(root, file))

print("\n🎉 All Python files processed successfully!")
print(f"Adapted for python-telegram-bot {'20+' if USE_NEW_API else '13.x'} API under Python {PY_VERSION}.")
