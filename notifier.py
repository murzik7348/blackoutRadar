from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Kyiv")

# Де лежить база користувачів
USER_DATA_PATH = os.getenv("USER_DATA_PATH", "user_data.json")

# Де лежать графіки
# Підтримує:
#   schedules/{region_code}_{YYYY-MM-DD}.json
#   schedules/{region_code}.json
SCHEDULE_DIR = os.getenv("SCHEDULE_DIR", "schedules")

# За скільки хвилин до старту відключення кидати нагадування
NOTIFY_LEAD_MINUTES = int(os.getenv("NOTIFY_LEAD_MINUTES", "60"))

# Як часто перевіряти
NOTIFY_CHECK_SECONDS = int(os.getenv("NOTIFY_CHECK_SECONDS", "60"))


@dataclass(frozen=True)
class Interval:
    start: time
    end: time

    @property
    def key(self) -> str:
        return f"{self.start.strftime('%H:%M')}-{self.end.strftime('%H:%M')}"


def _load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _save_json(path: str, data: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _parse_time(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def parse_intervals(raw_list: Any) -> List[Interval]:
    intervals: List[Interval] = []
    if not isinstance(raw_list, list):
        return intervals

    for item in raw_list:
        if not isinstance(item, dict):
            continue
        start_s = item.get("start")
        end_s = item.get("end")
        if not (isinstance(start_s, str) and isinstance(end_s, str)):
            continue
        try:
            st = _parse_time(start_s)
            en = _parse_time(end_s)
        except Exception:
            continue

        # Простий денний графік: якщо end <= start — ігноруємо
        if (en.hour, en.minute) <= (st.hour, st.minute):
            continue

        intervals.append(Interval(st, en))

    intervals.sort(key=lambda i: (i.start.hour, i.start.minute))
    return intervals


def _extract_schedule_mapping(doc: Dict[str, Any]) -> Dict[str, Any]:
    # підтримка двох форматів:
    # 1) {"schedule": {...}}
    # 2) {...} напряму
    if "schedule" in doc and isinstance(doc["schedule"], dict):
        return doc["schedule"]
    return doc


def load_schedule(region_code: str, target: date) -> Dict[str, List[Interval]]:
    day_str = target.isoformat()
    path_day = os.path.join(SCHEDULE_DIR, f"{region_code}_{day_str}.json")
    path_generic = os.path.join(SCHEDULE_DIR, f"{region_code}.json")

    doc: Dict[str, Any] = _load_json(path_day, {})
    if not doc:
        doc = _load_json(path_generic, {})

    mapping = _extract_schedule_mapping(doc) if isinstance(doc, dict) else {}
    result: Dict[str, List[Interval]] = {}

    if isinstance(mapping, dict):
        for k, v in mapping.items():
            result[str(k)] = parse_intervals(v)

    return result


def load_users() -> Dict[str, Any]:
    return _load_json(USER_DATA_PATH, {})


def save_users(data: Dict[str, Any]) -> None:
    _save_json(USER_DATA_PATH, data)


def _get_user_queue_key(user: Dict[str, Any]) -> Optional[str]:
    # Підтримка:
    # - "queue": "1.1"
    # - або "queue_main": 1, "queue_sub": 1
    q = user.get("queue")
    if isinstance(q, str) and q.strip():
        return q.strip()

    main = user.get("queue_main")
    sub = user.get("queue_sub")
    if isinstance(main, (int, str)) and isinstance(sub, (int, str)):
        return f"{main}.{sub}"

    return None


def _get_region_code(user: Dict[str, Any]) -> Optional[str]:
    # Підлаштуй під свої ключі, якщо треба
    region = user.get("region_code") or user.get("region") or user.get("oblast")
    if isinstance(region, str) and region.strip():
        return region.strip()
    return None


def _get_last_notified(user: Dict[str, Any]) -> Dict[str, Any]:
    ln = user.get("last_notified")
    return ln if isinstance(ln, dict) else {}


def _mark_notified(user: Dict[str, Any], target_date: date, interval_key: str) -> None:
    ln = _get_last_notified(user)
    day_key = target_date.isoformat()

    day_map = ln.get(day_key)
    if not isinstance(day_map, dict):
        day_map = {}

    day_map[interval_key] = datetime.now(TZ).isoformat()
    ln[day_key] = day_map
    user["last_notified"] = ln


def _already_notified(user: Dict[str, Any], target_date: date, interval_key: str) -> bool:
    ln = _get_last_notified(user)
    day_map = ln.get(target_date.isoformat())
    if not isinstance(day_map, dict):
        return False
    return interval_key in day_map


def _build_datetime(d: date, t: time) -> datetime:
    return datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=TZ)


def _next_intervals_with_lead(
    intervals: List[Interval], target_date: date
) -> List[Tuple[Interval, datetime]]:
    items: List[Tuple[Interval, datetime]] = []
    for iv in intervals:
        start_dt = _build_datetime(target_date, iv.start)
        notify_at = start_dt - timedelta(minutes=NOTIFY_LEAD_MINUTES)
        items.append((iv, notify_at))
    return items


def compute_due_notifications_for_user(
    user: Dict[str, Any], now: datetime
) -> List[Tuple[str, Interval, date]]:
    """
    Повертає список інтервалів, про які треба нагадати саме зараз.
    Логіка:
      - беремо графік на СЬОГОДНІ по user.region_code
      - шукаємо інтервали для user.queue
      - якщо зараз у вікні [start - lead, start)
        і ще не було повідомлення — шлемо.
    """
    region_code = _get_region_code(user)
    queue_key = _get_user_queue_key(user)
    if not region_code or not queue_key:
        return []

    sched = load_schedule(region_code, now.date())
    intervals = sched.get(queue_key, [])

    due: List[Tuple[str, Interval, date]] = []
    for iv, notify_at in _next_intervals_with_lead(intervals, now.date()):
        if _already_notified(user, now.date(), iv.key):
            continue

        start_dt = _build_datetime(now.date(), iv.start)
        if notify_at <= now < start_dt:
            due.append((queue_key, iv, now.date()))

    return due


# ---------- PTB JobQueue інтеграція ----------

async def notify_job(context) -> None:
    """
    Callback для Application.job_queue.
    user_data.json очікується у форматі:
      {
        "123456789": {
          "chat_id": 123456789,              # опційно
          "region_code": "zakarpattia",      # або region/oblast
          "queue": "1.1"                     # або queue_main/queue_sub
        }
      }
    """
    now = datetime.now(TZ)

    users = load_users()
    if not isinstance(users, dict) or not users:
        return

    changed = False

    for user_id_str, user in users.items():
        if not isinstance(user, dict):
            continue

        # chat_id беремо або з user, або ключа
        try:
            chat_id = int(user.get("chat_id") or user_id_str)
        except Exception:
            continue

        due = compute_due_notifications_for_user(user, now)
        if not due:
            continue

        for queue_key, iv, d in due:
            text = (
                "⚠️ Нагадування про відключення.\n"
                f"Черга: {queue_key}\n"
                f"Час: {iv.start.strftime('%H:%M')}–{iv.end.strftime('%H:%M')}\n"
                f"Дата: {d.strftime('%Y-%m-%d')}"
            )
            try:
                await context.bot.send_message(chat_id=chat_id, text=text)
                _mark_notified(user, d, iv.key)
                changed = True
            except Exception:
                # Не валимо весь цикл
                continue

    if changed:
        save_users(users)


def register_notify_jobs(application) -> None:
    """
    Викликати 1 раз після створення Application.
    """
    application.job_queue.run_repeating(
        notify_job,
        interval=NOTIFY_CHECK_SECONDS,
        first=10,
        name="blackout_notify",
    )
