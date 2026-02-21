import json, os, threading
from typing import Optional, Dict, Any

DB_PATH = os.getenv("USER_DB", "user_data.json")
_LOCK = threading.Lock()

def _load() -> Dict[str, Any]:
    if not os.path.exists(DB_PATH):
        return {"users": {}}
    with open(DB_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {"users": {}}

def _save(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    tmp = DB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DB_PATH)

def get_user(chat_id: int) -> Dict[str, Any]:
    with _LOCK:
        db = _load()
        return db["users"].get(str(chat_id), {})

def upsert_user(chat_id: int, **fields) -> Dict[str, Any]:
    with _LOCK:
        db = _load()
        u = db["users"].get(str(chat_id), {})
        u.update(fields)
        db["users"][str(chat_id)] = u
        _save(db)
        return u

def set_city(chat_id: int, city_id: str, city: str, oblast: str) -> Dict[str, Any]:
    return upsert_user(chat_id, city_id=city_id, city=city, oblast=oblast)

def set_queue(chat_id: int, queue: int) -> Dict[str, Any]:
    return upsert_user(chat_id, queue=int(queue))

def set_subqueue(chat_id: int, subqueue: Optional[str]) -> Dict[str, Any]:
    # subqueue format: "N-M" або None
    return upsert_user(chat_id, subqueue=subqueue)

def all_users() -> Dict[str, Any]:
    with _LOCK:
        return _load().get("users", {})
