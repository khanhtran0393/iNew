import asyncio
import threading
from typing import Coroutine, Optional


def spawn(coro: Coroutine) -> Optional[asyncio.Task]:
    """Safely spawn a fire-and-forget background asyncio task from any context (async or sync thread)."""
    try:
        loop = asyncio.get_running_loop()
        return loop.create_task(coro)
    except RuntimeError:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return asyncio.run_coroutine_threadsafe(coro, loop)
        except Exception:
            pass

        def _runner():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                new_loop.run_until_complete(coro)
            finally:
                new_loop.close()

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        return None
