"""HTTP media and file download utilities."""

import aiohttp
from pathlib import Path
from typing import Optional


async def download_file(url: str, dest_path: Path) -> bool:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=30) as resp:
                if resp.status == 200:
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(dest_path, "wb") as f:
                        while True:
                            chunk = await resp.content.read(65536)
                            if not chunk:
                                break
                            f.write(chunk)
                    return True
    except Exception:
        pass
    return False
