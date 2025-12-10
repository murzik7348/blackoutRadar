import aiohttp
import json
import datetime
import asyncio

DTEK_API = "https://api.dtek.com/schedule"   # ПОТРІБНО ЗАМІНИТИ НА РЕАЛЬНИЙ URL


async def fetch_dtek_schedule() -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(DTEK_API) as resp:
            if resp.status != 200:
                return {}

            data = await resp.json()
            return data


async def save_dtek(data: dict):
    with open("telegram_bot/data/dtek_schedule.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def update_dtek_schedule():
    data = await fetch_dtek_schedule()
    if data:
        await save_dtek(data)
    return data


if __name__ == "__main__":
    asyncio.run(update_dtek_schedule())
