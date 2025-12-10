from typing import Optional, List, Dict

def has_subqueues(sched: Dict) -> bool:
    return any("subqueue" in q for q in sched.get("queues", []))

def next_intervals_for_user(sched: Dict, queue: int, subqueue: Optional[str]) -> List[Dict]:
    """Повертає інтервали для конкретного юзера.
       Якщо в розкладі є підчерги і юзер НЕ обрав підчергу — беремо всі підчерги цієї черги (щоб не лишити без сповіщень)."""
    date = sched["date"]
    res = []
    qs = sched.get("queues", [])
    if has_subqueues(sched):
        for q in qs:
            if q.get("queue") != queue:
                continue
            if subqueue:
                if q.get("subqueue") == subqueue:
                    for a,b in q["intervals"]:
                        res.append({"start": f"{date} {a}", "end": f"{date} {b}"})
            else:
                # нема вибраної підчерги — беремо всі підчерги цієї черги
                for a,b in q["intervals"]:
                    res.append({"start": f"{date} {a}", "end": f"{date} {b}"})
    else:
        # розклад без підчерг
        for q in qs:
            if q.get("queue") == queue:
                for a,b in q["intervals"]:
                    res.append({"start": f"{date} {a}", "end": f"{date} {b}"})
    return res
