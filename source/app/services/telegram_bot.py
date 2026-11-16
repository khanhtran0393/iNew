"""Telegram Editorial Bot management and interactive message handlers."""

import logging
from app.config import settings

logger = logging.getLogger("ak_news.telegram_bot")

bot = None
dp = None

try:
    from aiogram import Bot, Dispatcher
except ImportError:
    Bot = None
    Dispatcher = None


def get_bot():
    global bot
    if not bot and settings.TELEGRAM_BOT_TOKEN and Bot:
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    return bot


async def dispatch_pending_outbox():
    # Outbox dispatcher implementation
    pass
