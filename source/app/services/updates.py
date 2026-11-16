"""Application self-update check against GitHub releases."""

import aiohttp
from typing import Optional, Dict, Any
from app.config import settings


async def check_for_updates() -> Optional[Dict[str, Any]]:
    if not settings.UPDATE_REPO:
        return None
    url = f"https://api.github.com/repos/{settings.UPDATE_REPO}/releases/latest"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    tag = data.get("tag_name", "").lstrip("v")
                    if tag and tag != settings.APP_VERSION:
                        return {
                            "has_update": True,
                            "latest_version": tag,
                            "url": data.get("html_url", "")
                        }
    except Exception:
        pass
    return None


async def check_loop():
    pass
