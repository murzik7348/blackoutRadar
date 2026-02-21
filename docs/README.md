# uk-blackout-ai — OCR сервіс для графіків відключення світла (UA)

**Що це:** локальний FastAPI сервіс, який приймає фото/скріни з графіками, робить OCR (Tesseract) і повертає структурований JSON: місто, дата, інтервали для кожної черги.

## Швидкий старт (локально)
1) Встанови Tesseract та українські моделі.
   - **macOS (Homebrew):**
     ```bash
     brew install tesseract
     brew install tesseract-lang
     # якщо не ставиться tesseract-lang: `brew install tesseract-ukrainian`
     which tesseract  # скопіюй шлях, наприклад /opt/homebrew/bin/tesseract
     ```
   - **Ubuntu/Debian:**
     ```bash
     sudo apt update
     sudo apt install -y tesseract-ocr tesseract-ocr-ukr tesseract-ocr-rus
     ```

2) Python залежності:
   ```bash
   cd ocr_service
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

3) (За потреби) Вкажи шлях до tesseract:
   ```bash
   export TESSERACT_CMD="/opt/homebrew/bin/tesseract"  # macOS M1/M2
   ```

4) Запуск сервісу:
   ```bash
   uvicorn app:app --host 0.0.0.0 --port 8000
   ```
   Перевірка: `GET http://localhost:8000/health` → `{"ok": true}`.

5) Витяг зображення (curl):
   ```bash
   curl -F "image=@/path/to/photo.jpg" http://localhost:8000/extract
   ```

## Запуск у Docker
```bash
cd ocr_service
docker build -t uk-blackout-ai .
docker run --rm -p 8000:8000 -e TESSERACT_CMD=tesseract uk-blackout-ai
```

## Інтеграція з твоїм Telegram-ботом (python-telegram-bot)
- Додай модуль `bot_integration/schedule_client.py` у свій репозиторій і викликай `extract_schedule(image_path)` після того, як бот завантажив фото від користувача.
- Отримаєш JSON з чергами та проміжками часу — збережи в свою БД/JSON і використовуй для сповіщень.

## Пакетна обробка папки
```bash
python batch_ingest.py --input /path/to/folder --out out_json
```
Для кожного зображення створить JSON файл із тим же ім’ям.

## Формат відповіді
```json
{
  "city": "Київ",
  "oblast": "Київська",
  "date": "2025-11-10",
  "queues": [
    {"queue": 1, "intervals": [["08:00","12:00"], ["20:00","24:00"]]},
    {"queue": 2, "intervals": [["12:00","16:00"]]}
  ],
  "source_hash": "sha256:...",
  "raw_text": "повний текст із OCR"
}
```
> **Примітка:** Парсер регексами заточений під типові шаблони: `черга/група N` і діапазони `HH:MM–HH:MM`. Легко розширюється правилами в `extract.py` → `parse_schedule()`.

## Ліцензія
MIT
