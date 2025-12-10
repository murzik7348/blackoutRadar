import json, os
from typing import Optional, Dict, Any

STORE = os.getenv("SCHEDULE_STORE", "schedules")
os.makedirs(STORE, exist_ok=True)

def save_schedule(sched: Dict[str, Any]) -> str:
    city_id = sched.get("city_id") or "unknown"
    date = sched["date"]
    path = os.path.join(STORE, f"{city_id}_{date}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sched, f, ensure_ascii=False, indent=2)
    return path

def load_schedule(city_id: str, date: str) -> Optional[Dict[str, Any]]:
    path = os.path.join(STORE, f"{city_id}_{date}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None
