
import json, os, threading
from typing import Dict, Any
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_DATA_FILE = os.getenv("USER_DATA_FILE", os.path.join(_PROJECT_ROOT, "user_data.json"))
_lock = threading.Lock()
def _load() -> Dict[str, Any]:
    if not os.path.exists(_DATA_FILE):
        return {}
    try:
        with open(_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}
def _save(db: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
    with open(_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
def upsert_user(chat_id: int, **fields: Any) -> Dict[str, Any]:
    key = str(chat_id)
    with _lock:
        db = _load()
        row = db.get(key, {})
        row.update({k: v for k, v in fields.items() if v is not None})
        db[key] = row
        _save(db)
        return row
def get_user(chat_id: int) -> Dict[str, Any]:
    key = str(chat_id)
    with _lock:
        db = _load()
        return db.get(key, {})
