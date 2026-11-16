"""Telethon user-client channel listener and real-time ingestion."""

import logging
from telethon import TelegramClient
from app.config import settings

logger = logging.getLogger("ak_news.telegram_ingestion")
client: TelegramClient = None


async def start():
    logger.info("Telethon ingestion started.")


async def stop():
    logger.info("Telethon ingestion stopped.")
