#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_inline_tables_patch.py -- minimal, idempotent patcher for inline tables (queues & subqueues N.N).

Usage:
  python apply_inline_tables_patch.py [path_to_repo]
  python apply_inline_tables_patch.py --restore [path_to_repo]

- Edits telegram_bot/main.py in place.
- Adds:
  * import InlineKeyboardMarkup/InlineKeyboardButton
  * QUEUE_COUNT and _kb_queue/_kb_sub helpers
  * cb_queue/cb_sub handlers
  * handler registrations inside run()
  * queue table show at end of cmd_start/on_city/on_city_text/on_location

Creates telegram_bot/main.py.bak before the first patch.
"""
import sys, os, re, shutil

UK_QUEUE_BLOCK = """
# ==== INLINE TABLES (added) ====
import os as _os_inline_tables
QUEUE_COUNT = int(_os_inline_tables.getenv("QUEUE_COUNT", "5"))  # скільки черг = стільки підчерг

def _kb_queue() -> InlineKeyboardMarkup:
    rows = []
    i = 1
    while i <= QUEUE_COUNT:
        row = [InlineKeyboardButton(f"Черга {i}", callback_data=f"queue:{i}")]
        if i + 1 <= QUEUE_COUNT:
            row.append(InlineKeyboardButton(f"Черга {i+1}", callback_data=f"queue:{i+1}"))
        rows.append(row)
        i += 2
    rows.append([InlineKeyboardButton("✖ Закрити", callback_data="queue:close")])
    return InlineKeyboardMarkup(rows)

def _kb_sub() -> InlineKeyboardMarkup:
    rows = []
    i = 1
    while i <= QUEUE_COUNT:
        row = [InlineKeyboardButton(f"Підчерга {i}.{i}", callback_data=f"sub:{i}")]
        if i + 1 <= QUEUE_COUNT:
            row.append(InlineKeyboardButton(f"Підчерга {i+1}.{i+1}", callback_data=f"sub:{i+1}"))
        rows.append(row)
        i += 2
    rows.append([InlineKeyboardButton("✖ Закрити", callback_data="sub:close")])
    return InlineKeyboardMarkup(rows)

async def cb_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data = (q.data or "").split(":", 1)
    if len(data) != 2:
        return
    val = data[1]
    if val == "close":
        try:
            await q.edit_message_text("Закрито.")
        except Exception:
            pass
        return
    if not val.isdigit():
        return
    n = int(val)
    if n < 1 or n > QUEUE_COUNT:
        return
    try:
        upsert_user(q.message.chat_id, queue=n)
    except Exception:
        pass
    try:
        await q.edit_message_text(f"Черга збережена: {n}")
    except Exception:
        pass
    await q.message.chat.send_message("Оберіть свою підчергу:", reply_markup=_kb_sub())

async def cb_sub(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data = (q.data or "").split(":", 1)
    if len(data) != 2:
        return
    val = data[1]
    if val == "close":
        try:
            await q.edit_message_text("Закрито.")
        except Exception:
            pass
        return
    if not val.isdigit():
        return
    n = int(val)
    if n < 1 or n > QUEUE_COUNT:
        return
    try:
        upsert_user(q.message.chat_id, subqueue=f"{n}.{n}")
    except Exception:
        pass
    try:
        await q.edit_message_text(f"Підчерга збережена: {n}.{n}")
    except Exception:
        pass
    await q.message.chat.send_message(_summary(q.message.chat_id))
# ==== /INLINE TABLES (added) ====
"""

ADD_QUEUE_SHOW = 'await update.effective_chat.send_message("Оберіть свою чергу:", reply_markup=_kb_queue())'

def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write(path, s):
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)

def ensure_inline_imports(src):
    if "InlineKeyboardMarkup" in src and "InlineKeyboardButton" in src:
        return src, False
    # Try to augment an existing 'from telegram import (' block
    pattern = r"from\s+telegram\s+import\s*\((.*?)\)"
    m = re.search(pattern, src, flags=re.DOTALL)
    if m:
        block = m.group(1)
        additions = []
        if "InlineKeyboardMarkup" not in block:
            additions.append("InlineKeyboardMarkup")
        if "InlineKeyboardButton" not in block:
            additions.append("InlineKeyboardButton")
        if additions:
            new_block = block.strip()
            if not new_block.endswith(","):
                new_block += ","
            new_block += " " + ", ".join(additions)
            src = src[:m.start(1)] + new_block + src[m.end(1):]
            return src, True
    # Fallback: add a new import after first telegram.ext import
    insert_after = re.search(r"from\s+telegram\.ext\s+import[\s\S]*?\)\s*", src)
    ins_pos = insert_after.end() if insert_after else 0
    line = "\nfrom telegram import InlineKeyboardMarkup, InlineKeyboardButton\n"
    src = src[:ins_pos] + line + src[ins_pos:]
    return src, True

def ensure_block(src, marker="INLINE TABLES (added)"):
    if marker in src:
        return src, False
    # insert after imports (after telegram imports)
    m = re.search(r"(?:from\s+telegram\.ext\s+import[\s\S]*?\)\s*)", src)
    pos = m.end() if m else 0
    return src[:pos] + "\n" + UK_QUEUE_BLOCK + "\n" + src[pos:], True

def ensure_handlers_registration(src):
    changed = False
    if "CallbackQueryHandler(cb_queue" not in src:
        run_start = re.search(r"def\s+run\s*\(\)\s*:\s*", src)
        if run_start:
            rp = re.search(r"app\.run_polling\(", src[run_start.end():])
            insert_at = run_start.end() + (rp.start() if rp else 0)
            reg = "\n    app.add_handler(CallbackQueryHandler(cb_queue, pattern=r\"^queue:\"))\n"
            src = src[:insert_at] + reg + src[insert_at:]
            changed = True
    if "CallbackQueryHandler(cb_sub" not in src:
        run_start = re.search(r"def\s+run\s*\(\)\s*:\s*", src)
        if run_start:
            rp = re.search(r"app\.run_polling\(", src[run_start.end():])
            insert_at = run_start.end() + (rp.start() if rp else 0)
            reg = "\n    app.add_handler(CallbackQueryHandler(cb_sub, pattern=r\"^sub:\"))\n"
            src = src[:insert_at] + reg + src[insert_at:]
            changed = True
    return src, changed

def add_queue_show_to_func(src, func_name):
    # Add queue show call near the end of a coroutine function if not present
    if ADD_QUEUE_SHOW in src:
        return src, False  # already somewhere
    pat = rf"async\s+def\s+{func_name}\s*\([\s\S]*?\):\s*(?:\n|.)*?\n(?=\s*def|\s*async\s+def|\Z)"
    m = re.search(pat, src)
    if not m:
        return src, False
    block = src[m.start():m.end()]
    if "_kb_queue()" in block:
        return src, False
    # insert before the end of the function block
    insert_pos = m.end() - 1
    indent = "    "
    insertion = f"\n{indent}{ADD_QUEUE_SHOW}\n"
    src = src[:insert_pos] + insertion + src[insert_pos:]
    return src, True

def main():
    restore = False
    args = [a for a in sys.argv[1:] if a.strip()]
    if args and args[0] == "--restore":
        restore = True
        args = args[1:]
    repo = args[0] if args else os.getcwd()
    main_path = os.path.join(repo, "telegram_bot", "main.py")
    if not os.path.exists(main_path):
        print("ERR: not found", main_path)
        sys.exit(2)

    bak_path = main_path + ".bak"
    if restore:
        if os.path.exists(bak_path):
            shutil.copyfile(bak_path, main_path)
            print("Restored from", bak_path)
        else:
            print("No backup found:", bak_path)
        return

    with open(main_path, "r", encoding="utf-8") as f:
        src = f.read()

    if not os.path.exists(bak_path):
        shutil.copyfile(main_path, bak_path)
        print("Backup written to", bak_path)

    changed_any = False

    # 1) imports
    src, ch = ensure_inline_imports(src); changed_any |= ch

    # 2) block with keyboards + callbacks
    src, ch = ensure_block(src); changed_any |= ch

    # 3) register handlers inside run()
    src, ch = ensure_handlers_registration(src); changed_any |= ch

    # 4) show queue table at end of these functions (if present)
    for fn in ("cmd_start", "on_city", "on_city_text", "on_location"):
        src, ch = add_queue_show_to_func(src, fn); changed_any |= ch

    if changed_any:
        with open(main_path, "w", encoding="utf-8") as f:
            f.write(src)
        print("Patched:", main_path)
    else:
        print("Nothing to change (already patched).")

if __name__ == "__main__":
    main()
