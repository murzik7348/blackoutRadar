
# Фікс помилки python-telegram-bot + urllib3 на Python 3.14

Запуск (macOS/Linux):
```bash
./run.sh
```

Запуск (Windows PowerShell):
```powershell
./run.ps1
```

Це створить venv, поставить правильні версії:
- python-telegram-bot==20.7
- urllib3<2  (щоб був `contrib.appengine`)
- python-dotenv (за потреби)

Далі стартує `python -m telegram_bot`, який підхоплює твій `main.py`/`bot.py`/тощо.
