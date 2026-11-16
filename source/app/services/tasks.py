"""Background async task queues and job dispatcher."""

import asyncio
from typing import Callable, Any

_task_queue = asyncio.Queue()


async def enqueue_task(func: Callable, *args, **kwargs):
    await _task_queue.put((func, args, kwargs))


async def task_worker_loop():
    while True:
        try:
            func, args, kwargs = await _task_queue.get()
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)
            _task_queue.task_done()
        except Exception:
            await asyncio.sleep(1)
