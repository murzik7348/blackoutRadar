# Inline Tables Patch (queues + subqueues N.N), NO restructure

Що робить патчер:
- Додає імпорти InlineKeyboardMarkup/Button.
- Додає `QUEUE_COUNT` і функції `_kb_queue()` та `_kb_sub()`.
- Додає callback-хендлери `cb_queue` і `cb_sub`.
- Реєструє їх у `run()`.
- В кінець `cmd_start`, `on_city`, `on_city_text`, `on_location` додає показ таблиці черг.

Ідемпотентний: якщо вже додано — вдруге нічого не змінить.
Перед першим застосуванням створює `telegram_bot/main.py.bak` (бекап).

## Як застосувати
```bash
cd /Users/dimamurza/Documents/GitHub/dimanapp/telegram_bot
python apply_inline_tables_patch.py .
```

## Як відкрутити назад
```bash
python apply_inline_tables_patch.py --restore .
```
