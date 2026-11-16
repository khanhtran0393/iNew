import re
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import SourceChannel, RawPost, RawPostStatus, MediaItem, MediaType
from app.services.deduplication import compute_text_hash, check_deduplication, normalize_post_text
from app.services.media_storage import (
    prepare_media_target_path,
    dedupe_media_item,
    verify_image_integrity,
    source_quota_allows,
    add_source_usage
)
from app.services.outbox_dispatcher import queue_post_notifications
from app.services.media_fetcher import download_image_to_disk

logger = logging.getLogger("ak_news.telegram_web")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
CHECK_INTERVAL = 120
FIRST_RUN_LIMIT = 15


def parse_preview_page(html: str, channel_username: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    items = []

    for msg in soup.find_all("div", class_=lambda c: c and "tgme_widget_message" in c):
        data_post = msg.get("data-post", "")
        if not data_post:
            continue

        parts = data_post.split("/")
        msg_id = int(parts[-1]) if len(parts) > 1 and parts[-1].isdigit() else 0

        # Message Text
        text_el = msg.find("div", class_="tgme_widget_message_text")
        raw_text = text_el.get_text(separator="\n").strip() if text_el else ""

        # Date & Time
        time_el = msg.find("time")
        dt_val = None
        if time_el and time_el.get("datetime"):
            try:
                dt_val = datetime.fromisoformat(time_el["datetime"].replace("Z", "+00:00"))
            except Exception:
                pass
        if not dt_val:
            dt_val = datetime.now(timezone.utc)

        # Photos
        photos = []
        for photo_wrap in msg.find_all("a", class_=lambda c: c and "tgme_widget_message_photo_wrap" in c):
            style = photo_wrap.get("style", "")
            match = re.search(r"background-image:url\('([^']+)'\)", style)
            if match:
                photos.append(match.group(1))

        # Videos
        has_video = bool(msg.find("i", class_="message_video_duration") or msg.find("video"))

        if raw_text or photos or has_video:
            items.append({
                "message_id": msg_id,
                "data_post": data_post,
                "text": raw_text,
                "date": dt_val,
                "photos": photos,
                "has_video": has_video,
                "source_url": f"https://t.me/{data_post}",
            })

    return items


async def sync_public_channels(client: Optional[httpx.AsyncClient] = None) -> Dict[str, Any]:
    db: Session = SessionLocal()
    total_new = 0
    total_dups = 0
    total_channels = 0
    failed_channels = 0

    owns_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers={"User-Agent": UA})
        owns_client = True

    try:
        # Fetch all active public Telegram channels
        channels = (
            db.query(SourceChannel)
            .filter(
                SourceChannel.source_type == "telegram",
                SourceChannel.is_active == True,
                SourceChannel.username.isnot(None)
            )
            .all()
        )
        total_channels = len(channels)

        for sc in channels:
            username = sc.username.strip().lstrip("@")
            if not username:
                continue

            preview_url = f"https://t.me/s/{username}"
            try:
                resp = await client.get(preview_url)
                if resp.status_code != 200:
                    logger.warning(f"Failed to fetch Telegram preview for @{username}: HTTP {resp.status_code}")
                    failed_channels += 1
                    continue

                parsed_items = parse_preview_page(resp.text, username)
                for item in parsed_items[-FIRST_RUN_LIMIT:]:
                    msg_id = item["message_id"]
                    if not msg_id:
                        continue

                    # Check if already saved
                    existing = (
                        db.query(RawPost)
                        .filter(RawPost.source_id == sc.id, RawPost.telegram_message_id == msg_id)
                        .first()
                    )
                    if existing:
                        total_dups += 1
                        continue

                    text = item["text"]
                    text_hash = compute_text_hash(text) if text else None

                    # Check deduplication
                    is_dup = False
                    if text:
                        norm = normalize_post_text(text)
                        is_dup, dup_id = check_deduplication(db, norm)

                    post = RawPost(
                        source_id=sc.id,
                        telegram_message_id=msg_id,
                        cleaned_text=text,
                        text_hash=text_hash,
                        source_url=item["source_url"],
                        status=RawPostStatus.DUPLICATE.value if is_dup else RawPostStatus.NEW.value,
                        created_at=item["date"],
                    )
                    db.add(post)
                    db.flush()

                    # Download and attach photos
                    for idx, photo_url in enumerate(item["photos"][:5]):
                        if not source_quota_allows(db, sc.id):
                            break
                        tgt_path = prepare_media_target_path(post.id, f"photo_{idx}.jpg")
                        ok = await download_image_to_disk(photo_url, tgt_path, client=client)
                        if ok and tgt_path.exists():
                            m_item = MediaItem(
                                post_id=post.id,
                                media_type=MediaType.PHOTO.value,
                                local_path=str(tgt_path),
                                file_size=tgt_path.stat().st_size,
                            )
                            db.add(m_item)
                            add_source_usage(db, sc.id, tgt_path.stat().st_size)

                    db.commit()
                    total_new += 1

                    if not is_dup:
                        queue_post_notifications(post)

            except Exception as e:
                logger.error(f"Error scraping @{username}: {e}")
                failed_channels += 1

        summary = {
            "total_channels": total_channels,
            "new_posts": total_new,
            "duplicates": total_dups,
            "failed_channels": failed_channels,
        }
        logger.info(f"Telegram public sync: {total_new} posts from {total_channels} channels ({failed_channels} failed)")
        return summary
    finally:
        db.close()
        if owns_client:
            await client.aclose()


async def telegram_web_worker_loop(interval_seconds: int = CHECK_INTERVAL):
    logger.info("Public-channel Telegram collector ready (used while the Telegram account is not logged in).")
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers={"User-Agent": UA}) as client:
        while True:
            try:
                await sync_public_channels(client=client)
            except Exception as e:
                logger.error(f"Telegram public sync error: {e}")
            await asyncio.sleep(interval_seconds)
