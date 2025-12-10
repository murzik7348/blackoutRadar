
import os, sys, runpy
PKG_DIR = os.path.dirname(__file__)
ROOT = os.path.dirname(PKG_DIR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

override = os.getenv("TBOT_ENTRY")
candidates = []
if override:
    candidates.append(os.path.join(ROOT, override))

candidates += [
    os.path.join(ROOT, "telegram_bot", "main.py"),
    os.path.join(ROOT, "main.py"),
    os.path.join(ROOT, "bot.py"),
    os.path.join(ROOT, "app.py"),
    os.path.join(ROOT, "run.py"),
    os.path.join(ROOT, "start.py"),
]
for p in candidates:
    if os.path.exists(p):
        runpy.run_path(p, run_name="__main__")
        break
else:
    raise SystemExit("Не знайшов вхідний скрипт. Поклади main.py або вкажи TBOT_ENTRY")
