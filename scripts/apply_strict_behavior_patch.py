#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_strict_behavior_patch.py — точковий патч без зміни структури:
- /start: лише запит гео/міста (без таблиці черг)
- on_city: сувора валідація міста через Nominatim (UA only). Якщо не знайдено — просить повторити, НЕ показує черги
- on_location: реверс-геокод → збереження міста/області, лише тоді таблиця черг
- додає httpx імпорт та утиліти геокоду (_nominatim_get, reverse_geocode, strict_city_resolve)
Використання:
  python apply_strict_behavior_patch.py .
Відкат:
  python apply_strict_behavior_patch.py --restore .
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

def ensure_httpx_import(src: str):
    if "import httpx" in src or "import httpx as _httpx_strict" in src:
        return src, False
    # add simple import after other imports
    m = re.search(r"^import .*\\n", src, flags=re.MULTILINE)
    pos = m.end() if m else 0
    return src[:pos] + "import httpx\\n" + src[pos:], True

def ensure_geo_block(src: str):
    if "GEO STRICT (added)" in src:
        return src, False
    # insert after telegram imports
    m = re.search(r"(?:from\\s+telegram\\.ext\\s+import[\\s\\S]*?\\)\\s*)", src)
    pos = m.end() if m else 0
    return src[:pos] + "\\n" + GEO_BLOCK + "\\n" + src[pos:], True

def replace_function_body(src: str, fname: str, new_body: str):
    # Replace async def fname(...) : <block>
    pat = rf"(async\\s+def\\s+{fname}\\s*\\([\\s\\S]*?\\):)([\\s\\S]*?)(?=\\n\\s*async\\s+def|\\n\\s*def|\\Z)"
    m = re.search(pat, src)
    if not m:
        return src, False
    header = m.group(1)
    # keep original indentation of function body (4 spaces typical)
    indent = "    "
    src2 = src[:m.start()] + header + "\\n" + indent + new_body.strip() + "\\n" + src[m.end():]
    return src2, True

def remove_queue_show_in_start(src: str):
    # remove our queue show line inside cmd_start if present
    line = 'await update.effective_chat.send_message("Оберіть свою чергу:", reply_markup=_kb_queue())'
    if line not in src:
        return src, False
    pat = re.escape(line)
    return re.sub(pat + "\\n?", "", src), True

def ensure_backup(path):
    bak = path + ".bak2"
    if not os.path.exists(bak):
        shutil.copyfile(path, bak)
        print("Backup written to", bak)

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

    bak_path = main_path + ".bak2"
    if restore:
        if os.path.exists(bak_path):
            shutil.copyfile(bak_path, main_path)
            print("Restored from", bak_path)
        else:
            print("No backup found:", bak_path)
        return

    src = read(main_path)
    ensure_backup(main_path)
    changed = False

    # add geo block + httpx import
    src, ch = ensure_geo_block(src); changed |= ch
    src, ch = ensure_httpx_import(src); changed |= ch

    # cmd_start: leave only greeting + geo keyboard (видаляємо показ черг)
    src, ch = remove_queue_show_in_start(src); changed |= ch

    # on_city strict body
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
    src, ch = replace_function_body(src, "on_city", on_city_body); changed |= ch

    # on_location strict body
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
    src, ch = replace_function_body(src, "on_location", on_loc_body); changed |= ch

    if changed:
        write(main_path, src)
        print("Patched:", main_path)
    else:
        print("Nothing to change.")

if __name__ == "__main__":
    main()
