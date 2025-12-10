#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_strict_behavior_patch_v2.py — точковий патч без зміни структури:
- /start: прибирає показ черг (видаляє будь-які виклики _kb_queue() у cmd_start)
- on_city: сувора валідація міста через Nominatim (UA only). Якщо не знайдено — просить повторити і НЕ показує черги
- on_location: реверс-геокод → збереження міста/області; лише тоді показ таблиці черг
- додає блок утиліт геокоду (GEO STRICT) з httpx (локальний alias, не чіпає глобальні імпорти)
Використання:
  python apply_strict_behavior_patch_v2.py .
Відкат:
  python apply_strict_behavior_patch_v2.py --restore .
"""
import os, sys, re, shutil

GEO_BLOCK = """
# ==== GEO STRICT (added) ====
import httpx as _httpx_strict
_NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
_NOM_TIMEOUT = float(os.getenv("NOMINATIM_TIMEOUT", "2"))
_NOM_HEADERS = {"User-Agent": os.getenv("NOMINATIM_UA", "tg-bot/1.0 (+contact)"), "Accept-Language": "uk"}

async def _nominatim_get(path: str, params: dict):
    url = f"{_NOMINATIM_BASE.rstrip('/')}/{path.lstrip('/')}"
    timeout = _httpx_strict.Timeout(connect=_NOM_TIMEOUT, read=_NOM_TIMEOUT, write=_NOM_TIMEOUT, pool=_NOM_TIMEOUT)
    async with _httpx_strict.AsyncClient(headers=_NOM_HEADERS, timeout=timeout) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

async def reverse_geocode(lat: float, lon: float):
    for zoom in (15, 13, 10):
        try:
            data = await _nominatim_get("/reverse", {
                "lat": lat, "lon": lon, "format": "json", "zoom": zoom,
                "addressdetails": 1, "accept-language": "uk", "countrycodes": "ua"
            })
        except Exception:
            data = None
        if isinstance(data, dict):
            addr = data.get("address") or {}
            city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality")
            region = addr.get("state") or addr.get("region")
            if city or region:
                return city, region
    return None, None

async def strict_city_resolve(q: str):
    q = (q or "").strip()
    if not q:
        return None, None, False
    try:
        arr = await _nominatim_get("/search", {
            "q": q, "format": "json", "limit": 1, "addressdetails": 1,
            "accept-language": "uk", "countrycodes": "ua"
        })
    except Exception:
        arr = None
    if not (isinstance(arr, list) and arr):
        return None, None, False
    try:
        lat = float(arr[0]["lat"]); lon = float(arr[0]["lon"])
    except Exception:
        return None, None, False
    city, region = await reverse_geocode(lat, lon)
    if not (city and region):
        return None, None, False
    return city, region, True
# ==== /GEO STRICT (added) ====
"""

def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()

def write(p, s):
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)

def insert_after_imports(src: str, block: str) -> str:
    """
    Вставляє block відразу після блоку імпортів telegram/telegram.ext.
    Без небезпечних regex — простий пошук.
    """
    idx = src.find("from telegram.ext import")
    if idx == -1:
        # fallback: після першого імпорту
        m = re.search(r"^.*import.*\n", src, flags=re.MULTILINE)
        pos = m.end() if m else 0
        return src[:pos] + "\n" + block + "\n" + src[pos:]
    # знайти кінець дужки ')'
    close = src.find(")", idx)
    if close == -1:
        close = idx
    pos = close + 1
    return src[:pos] + "\n" + block + "\n" + src[pos:]

def ensure_geo_block(src: str):
    if "GEO STRICT (added)" in src:
        return src, False
    return insert_after_imports(src, GEO_BLOCK), True

def remove_queue_calls_in_func(src: str, func_name: str):
    """
    Прибирає рядки з _kb_queue() всередині зазначеної функції.
    """
    pat = rf"(async\s+def\s+{func_name}\s*\([\s\S]*?\):)([\s\S]*?)(?=\n\s*async\s+def|\n\s*def|\Z)"
    m = re.search(pat, src)
    if not m:
        return src, False
    header, body = m.group(1), m.group(2)
    new_body = re.sub(r".*_kb_queue\(\).*\n", "", body)
    if new_body == body:
        return src, False
    return src[:m.start()] + header + new_body + src[m.end():], True

def replace_function_body(src: str, fname: str, new_body: str):
    pat = rf"(async\s+def\s+{fname}\s*\([\s\S]*?\):)([\s\S]*?)(?=\n\s*async\s+def|\n\s*def|\Z)"
    m = re.search(pat, src)
    if not m:
        return src, False
    header = m.group(1)
    indent = "    "
    return src[:m.start()] + header + "\n" + indent + new_body.strip() + "\n" + src[m.end():], True

def ensure_backup(path, suffix=".sbak"):
    bak = path + suffix
    if not os.path.exists(bak):
        shutil.copyfile(path, bak)
        print("Backup written to", bak)
    return bak

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

    bak = ensure_backup(main_path)
    if restore:
        shutil.copyfile(bak, main_path)
        print("Restored from", bak)
        return

    src = read(main_path)
    changed = False

    # 1) GEO strict block
    src2, ch = ensure_geo_block(src); src = src2; changed |= ch

    # 2) /start — прибрати показ черг
    src2, ch = remove_queue_calls_in_func(src, "cmd_start"); src = src2; changed |= ch

    # 3) on_city — строгий резолв
    on_city_body = """
text = (update.message.text or "").strip()
city, region, ok = await strict_city_resolve(text)
if not ok:
    await update.effective_chat.send_message(
        "Не знайшов таке місто в Україні. Надішли геолокацію або напиши назву міста ще раз."
    )
    return
try:
    upsert_user(update.effective_chat.id, city=city, region=region)
except Exception:
    pass
await update.effective_chat.send_message("Оберіть свою чергу:", reply_markup=_kb_queue())
"""
    src2, ch = replace_function_body(src, "on_city", on_city_body); src = src2; changed |= ch

    # 4) on_location — reverse geocode + далі показ черг
    on_loc_body = """
loc = update.message.location
lat, lon = float(loc.latitude), float(loc.longitude)
city, region = await reverse_geocode(lat, lon)
if not (city or region):
    await update.effective_chat.send_message(
        "Не вдалось визначити місто. Напиши назву міста текстом."
    )
    return
try:
    upsert_user(update.effective_chat.id, city=city, region=region, lat=lat, lon=lon)
except Exception:
    pass
await update.effective_chat.send_message("Гео збережено ✅", reply_markup=ReplyKeyboardRemove())
await update.effective_chat.send_message("Оберіть свою чергу:", reply_markup=_kb_queue())
"""
    src2, ch = replace_function_body(src, "on_location", on_loc_body); src = src2; changed |= ch

    if changed:
        write(main_path, src)
        print("Patched:", main_path)
    else:
        print("Nothing to change.")

if __name__ == "__main__":
    main()
