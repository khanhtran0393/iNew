import re
import logging
from typing import Dict, Any, Tuple, Optional
import httpx

from app.config import settings

logger = logging.getLogger("ak_news.updates")

# Cache to prevent frequent API calls
_CACHED_RESULT: Optional[Dict[str, Any]] = None


def _version_tuple(v: str) -> Tuple[int, ...]:
    clean = re.sub(r"[^\d\.]", "", v.strip())
    parts = []
    for part in clean.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts) if parts else (0, 0, 0)


async def check_for_updates(force: bool = False) -> Dict[str, Any]:
    global _CACHED_RESULT
    if not force and _CACHED_RESULT is not None:
        return _CACHED_RESULT

    current_v = settings.VERSION
    current_tup = _version_tuple(current_v)

    res = {
        "has_update": False,
        "current_version": current_v,
        "latest_version": current_v,
        "download_url": "",
        "release_notes": "",
        "published_at": "",
    }

    update_url = getattr(settings, "UPDATE_CHECK_URL", "https://api.github.com/repos/inew-news/inew-app/releases/latest")
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(
                update_url,
                headers={"User-Agent": f"iNew-Desktop/{current_v}"}
            )
            if resp.status_code == 200:
                data = resp.json()
                tag = data.get("tag_name", "").lstrip("v")
                latest_tup = _version_tuple(tag)
                if latest_tup > current_tup:
                    res["has_update"] = True
                    res["latest_version"] = tag
                    res["release_notes"] = data.get("body", "")
                    res["published_at"] = data.get("published_at", "")
                    
                    # Find binary download url
                    for asset in data.get("assets", []):
                        if asset.get("name", "").endswith((".exe", ".zip")):
                            res["download_url"] = asset.get("browser_download_url", "")
                            break
                    if not res["download_url"]:
                        res["download_url"] = data.get("html_url", "")
    except Exception as e:
        logger.debug(f"Update check query skipped or failed: {e}")

    _CACHED_RESULT = res
    return res


def get_cached_update_info() -> Dict[str, Any]:
    if _CACHED_RESULT is not None:
        return _CACHED_RESULT
    return {
        "has_update": False,
        "current_version": settings.VERSION,
        "latest_version": settings.VERSION,
        "download_url": "",
        "release_notes": "",
    }
