"""Periodic storage and maintenance cleanup worker."""

import asyncio
from app.services.media_storage import cleanup_stale_media
from app.config import settings


async def maintenance_worker_loop():
    while True:
        try:
            cleanup_stale_media(settings.MEDIA_RETENTION_DAYS)
            await asyncio.sleep(86400)
        except Exception:
            break
