import aiohttp
import json
import asyncio

ZAK_API = "https://zakarpattia.energy/api/outages"   # ПОТРІБНО ЗАМІНИТИ НА РЕАЛЬНИЙ URL


async def fetch_zak_schedule():
    async with aiohttp.ClientSession() as session:
        async with session.get(ZAK_API) as resp:
            if resp.status != 200:
                return {}

            return await resp.json()


async def save_zak(data: dict):
    with open("telegram_bot/data/zakarpattia_schedule.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def update_zak_schedule():
    data = await fetch_zak_schedule()
    if data:
        await save_zak(data)
    return data


if __name__ == "__main__":
    asyncio.run(update_zak_schedule())
