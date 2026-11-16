"""Background worker for automated video production."""

import asyncio


async def auto_video_worker_loop():
    while True:
        try:
            await asyncio.sleep(60)
        except Exception:
            break
