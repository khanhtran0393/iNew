"""Public Telegram Web preview scraper (fallback mode)."""

import asyncio


async def telegram_web_worker_loop():
    while True:
        try:
            await asyncio.sleep(120)
        except Exception:
            break
