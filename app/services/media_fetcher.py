import os
import re
import ipaddress
import logging
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

import httpx
from PIL import Image

from app.config import settings

logger = logging.getLogger("ak_news.media_fetcher")

MAX_IMAGE_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_MEDIA_DOWNLOAD_SIZE_MB = 100
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}


def is_public_http_url(url: str) -> bool:
    """Validate that URL is public HTTP/HTTPS to prevent SSRF vulnerabilities."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        hostname = hostname.lower()
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return False
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        except ValueError:
            pass  # Hostname is a domain name, proceed
        return True
    except Exception:
        return False


async def download_image_to_disk(
    url: str,
    target_path: Path,
    client: Optional[httpx.AsyncClient] = None,
    max_bytes: int = MAX_IMAGE_BYTES
) -> bool:
    if not is_public_http_url(url):
        logger.warning(f"Blocked non-public media URL: {url}")
        return False

    target_path = Path(target_path)
    part_path = target_path.with_suffix(target_path.suffix + ".part")
    target_path.parent.mkdir(parents=True, exist_ok=True)

    owns_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=BROWSER_HEADERS)
        owns_client = True

    try:
        async with client.stream("GET", url) as resp:
            if resp.status_code != 200:
                logger.warning(f"Could not download image from {url}: HTTP {resp.status_code}")
                return False

            total = 0
            with open(part_path, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=16384):
                    total += len(chunk)
                    if total > max_bytes:
                        logger.warning(f"Image too large (> {max_bytes} bytes): {url}")
                        part_path.unlink(missing_ok=True)
                        return False
                    f.write(chunk)

        # Verify image integrity via PIL
        try:
            with Image.open(part_path) as img:
                img.verify()
        except Exception as e:
            logger.warning(f"Image integrity verification failed for {url}: {e}")
            part_path.unlink(missing_ok=True)
            return False

        if part_path.exists():
            part_path.replace(target_path)
            return True
        return False
    except Exception as e:
        logger.error(f"Download failed for {url}: {e}")
        part_path.unlink(missing_ok=True)
        return False
    finally:
        if owns_client:
            await client.aclose()


def download_video_yt_dlp(url: str, output_template: str) -> Optional[str]:
    """Extract standalone video using yt-dlp if installed/available."""
    if not is_public_http_url(url):
        return None
    try:
        import yt_dlp
        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "max_filesize": MAX_MEDIA_DOWNLOAD_SIZE_MB * 1024 * 1024,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        logger.warning(f"yt-dlp could not extract standalone video from {url}: {e}")
        return None


async def download_media_file(url: str, target_path: str) -> bool:
    """Download a remote media URL directly to a specified local path."""
    tgt = Path(target_path)
    return await download_image_to_disk(url, tgt)


async def download_media_for_post(post_id: int) -> bool:
    """Download all remote media items associated with a given post."""
    from app.database import SessionLocal
    from app.models import RawPost, MediaItem
    from app.services.media_storage import prepare_media_target_path

    db = SessionLocal()
    try:
        post = db.query(RawPost).filter_by(id=post_id).first()
        if not post:
            return False

        updated = False
        for idx, item in enumerate(post.media_items):
            fp = item.file_path or ""
            if fp.startswith("http"):
                ext = ".mp4" if item.media_type == "video" else ".jpg"
                tgt_path = prepare_media_target_path(post_id, f"media_{idx}{ext}")
                ok = await download_media_file(fp, str(tgt_path))
                if ok and tgt_path.exists():
                    item.file_path = str(tgt_path)
                    item.file_size_bytes = tgt_path.stat().st_size
                    updated = True

        if updated:
            db.commit()
        return True
    except Exception as e:
        logger.error(f"download_media_for_post failed for #{post_id}: {e}")
        return False
    finally:
        db.close()
