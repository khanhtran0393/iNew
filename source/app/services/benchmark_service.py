"""Benchmark evaluation service worker."""

import asyncio


async def benchmark_worker_loop():
    while True:
        try:
            await asyncio.sleep(3600)
        except Exception:
            break
