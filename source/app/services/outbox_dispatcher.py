"""Background outbox dispatcher worker loop."""

import asyncio
from app.services.telegram_bot import dispatch_pending_outbox


async def outbox_worker_loop():
    while True:
        try:
            await dispatch_pending_outbox()
            await asyncio.sleep(5)
        except Exception:
            await asyncio.sleep(5)
