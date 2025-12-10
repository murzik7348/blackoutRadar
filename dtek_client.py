# telegram_bot/dtek_client.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import aiohttp
import pytz

KYIV_TZ = pytz.timezone("Europe/Kyiv")


class DTEKClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class OutageInterval:
    start: datetime  # aware (Europe/Kyiv)
    end: datetime    # aware (Europe/Kyiv)


class DTEKClient:
    """
    Обережний клієнт:
    1) Пробує отримати JSON з офіційного API (очікувана форма).
    2) Якщо формат/відповідь не підходить — фолбек у локальний МОК.
    """

    def __init__(
        self,
        base_url: str = "https://www.dtek.com/api/v1/outage-schedule",
        mock_path: str | None = None,
        timeout_sec: int = 15,
        use_mock_on_fail: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout_sec)
        self.use_mock_on_fail = use_mock_on_fail
        self.mock_path = mock_path or os.path.join(
            os.path.dirname(__file__), "mock_regions.json"
        )
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, *exc):
        if self._session:
            await self._session.close()
            self._session = None

    # ---------- ПУБЛІЧНЕ АПІ ----------

    async def get_city_queue_outages(
        self, city_name: str, queue: str
    ) -> List[OutageInterval]:
        """
        Інтервали відключень для міста+черги (в Europe/Kyiv).
        """
        try:
            return await self._from_api(city_name, queue)
        except Exception as e:
            if not self.use_mock_on_fail:
                raise
            print(f"⚠️ DTEK API недоступний/неочікуваний формат ({e}). Використовую МОК.")
            return self._from_mock(city_name, queue)

    # ---------- ВНУТРІШНЄ ----------

    async def _get_json(self, url: str, params: dict | None = None) -> dict | list:
        assert self._session is not None
        headers = {
            "Accept": "application/json; charset=utf-8",
            "User-Agent": "Mozilla/5.0 (compatible; DTEKBot/1.0)",
            "Cache-Control": "no-cache",
        }
        async with self._session.get(url, params=params, headers=headers) as resp:
            ctype = resp.headers.get("Content-Type", "")
            text = await resp.text()
            if "application/json" not in ctype.lower():
                raise DTEKClientError(
                    f"Expected JSON, got {ctype!r}; body starts: {text[:120]!r}"
                )
            try:
                return json.loads(text)
            except json.JSONDecodeError as e:
                raise DTEKClientError(f"Invalid JSON: {e}: {text[:120]!r}") from e

    async def _from_api(self, city_name: str, queue: str) -> List[OutageInterval]:
        # 1) регіони
        regions_url = f"{self.base_url}/regions"
        regions = await self._get_json(regions_url)
        region_ids = [
            r.get("id") for r in regions if isinstance(regions, list) and isinstance(r, dict)
        ]
        if not region_ids:
            raise DTEKClientError("regions list is empty or unexpected")

        # 2) локалії -> пошук по назві міста
        target_loc_id: Optional[int] = None
        city_cf = city_name.casefold()
        for rid in region_ids:
            locs_url = f"{self.base_url}/regions/{rid}/localities"
            locs = await self._get_json(locs_url)
            if not isinstance(locs, list):
                continue
            for loc in locs:
                if not isinstance(loc, dict):
                    continue
                name = (loc.get("name") or "").casefold()
                if name == city_cf or city_cf in name:
                    target_loc_id = loc.get("id")
                    break
            if target_loc_id:
                break

        if not target_loc_id:
            raise DTEKClientError(f"locality not found for city={city_name!r}")

        # 3) графік локалії — пробуємо декілька варіантів
        schedules_payload = None
        for endpoint in ("schedules", "outages", "schedule"):
            try:
                url = f"{self.base_url}/localities/{target_loc_id}/{endpoint}"
                schedules_payload = await self._get_json(url)
                break
            except Exception:
                continue
        if schedules_payload is None:
            raise DTEKClientError("no schedule endpoint worked")

        # 4) парс у список інтервалів для queue
        # Очікуємо щось на кшталт:
        # {"groups":[{"queue":"1","intervals":[{"start":"YYYY-MM-DDTHH:MM","end":"..."}]}]}
        if not isinstance(schedules_payload, dict):
            raise DTEKClientError("unexpected JSON (not object)")

        groups = schedules_payload.get("groups")
        if not isinstance(groups, list):
            raise DTEKClientError("unexpected schedules JSON shape (no 'groups')")

        out: List[OutageInterval] = []
        for g in groups:
            if not isinstance(g, dict):
                continue
            if str(g.get("queue")) != str(queue):
                continue
            for it in g.get("intervals", []):
                if not isinstance(it, dict):
                    continue
                s = self._parse_dt_kyiv(it.get("start"))
                e = self._parse_dt_kyiv(it.get("end"))
                if s and e and e > s:
                    out.append(OutageInterval(start=s, end=e))
        return out

    def _from_mock(self, city_name: str, queue: str) -> List[OutageInterval]:
        if not os.path.exists(self.mock_path):
            return []
        with open(self.mock_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # МОК-формат:
        # { "Київ": { "1": [["2025-10-26T18:00","2025-10-26T20:00"], ...], "2": [...], "3": [...] } }
        city = data.get(city_name) if isinstance(data, dict) else None
        if not isinstance(city, dict):
            return []
        raw = city.get(str(queue))
        if not isinstance(raw, list):
            return []
        out: List[OutageInterval] = []
        for pair in raw:
            if not (isinstance(pair, list) and len(pair) == 2):
                continue
            s = self._parse_dt_kyiv(pair[0])
            e = self._parse_dt_kyiv(pair[1])
            if s and e and e > s:
                out.append(OutageInterval(start=s, end=e))
        return out

    def _parse_dt_kyiv(self, s: str | None) -> Optional[datetime]:
        if not s:
            return None
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(s, fmt)
                return KYIV_TZ.localize(dt)
            except ValueError:
                continue
        return None
