"""Telegram notifications dispatcher for staff alerts."""

import logging
from app.config import settings

logger = logging.getLogger("ak_news.staff_notify")


async def notify_staff(text: str, chat_id: int = 0):
    if not settings.TELEGRAM_BOT_TOKEN:
        return
    target = chat_id or settings.TELEGRAM_DEFAULT_EDITORIAL_CHAT_ID
    if not target:
        return
    try:
        import aiohttp
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        async with aiohttp.ClientSession() as session:
            await session.post(url, json={"chat_id": target, "text": text, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        logger.error(f"Failed to notify staff: {e}")
