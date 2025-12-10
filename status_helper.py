from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, time
from typing import List, Dict

from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Kyiv")


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime


def _to_today_interval(day: date, start: time, end: time) -> Interval:
    return Interval(
        start=datetime.combine(day, start, tzinfo=TZ),
        end=datetime.combine(day, end, tzinfo=TZ),
    )


def get_today_intervals_for_queue(queue_code: str) -> List[Interval]:
    """
    Повертає список інтервалів відключення на сьогодні для конкретної черги.

    !!! ТУТ ТИ ПІДКЛЮЧАЄШ СВІЙ РОЗКЛАД !!!
    Зараз тут пустий RAW_SCHEDULE, щоб код не падав.

    Приклад:
        RAW_SCHEDULE = {
            "5.1": [(time(15, 30), time(19, 0))],
            "3.2": [(time(9, 0), time(12, 0)), (time(18, 0), time(21, 0))],
        }
    """

    today = datetime.now(TZ).date()

    RAW_SCHEDULE: Dict[str, List[tuple[time, time]]] = {
        # TODO: заповни своїми інтервалами або заміни на виклик бекенду
        # "5.1": [(time(15, 30), time(19, 0))],
    }

    raw_intervals = RAW_SCHEDULE.get(queue_code, [])
    return [_to_today_interval(today, start, end) for start, end in raw_intervals]


def _format_eta(delta_seconds: float) -> str:
    """Форматує різницю в секундах типу '1 год 20 хв' / '45 хв'."""
    if delta_seconds <= 0:
        return "кілька хвилин"

    total_minutes = int(delta_seconds // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    parts: List[str] = []
    if hours > 0:
        parts.append(f"{hours} год")
    if minutes > 0 or not parts:
        parts.append(f"{minutes} хв")
    return " ".join(parts)


def build_current_status_text(queue_code: str) -> str:
    """
    Формує текст для юзера:
    - якщо зараз відключення: пише, що світла нема і коли включать + через скільки часу
    - якщо відключення ще буде: пише, коли наступне
    - якщо вже все було: пише, що на сьогодні все
    """
    now = datetime.now(TZ)
    intervals = get_today_intervals_for_queue(queue_code)

    if not intervals:
        return (
            "🔎 Поточний стан по вашій черзі:\n"
            "На сьогодні відключень за цією чергою не знайдено."
        )

    current: Interval | None = None
    next_interval: Interval | None = None

    for interval in intervals:
        if interval.start <= now < interval.end:
            current = interval
            break
        if now < interval.start:
            next_interval = interval
            break

    # 🔴 ВАРІАНТ: світла зараз немає
    if current is not None:
        remaining_sec = (current.end - now).total_seconds()
        eta_text = _format_eta(remaining_sec)
        return (
            "🚫 Світло зараз ВИМКНЕНЕ.\n"
            f"Планове відключення з {current.start:%H:%M} до {current.end:%H:%M}.\n"
            f"Світло має зʼявитися приблизно о {current.end:%H:%M} (через {eta_text})."
        )

    # 🟡 Світло є, але ще буде відключення
    if next_interval is not None:
        return (
            "✅ Світло зараз Є.\n"
            f"Наступне відключення з {next_interval.start:%H:%M} "
            f"до {next_interval.end:%H:%M}."
        )

    # 🟢 Всі відключення на сьогодні вже пройшли
    last_interval = intervals[-1]
    return (
        "✅ Світло зараз Є.\n"
        f"Сьогодні останнє відключення було з {last_interval.start:%H:%M} "
        f"до {last_interval.end:%H:%M}. Нових на сьогодні не заплановано."
    )
