import os
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
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

logger = logging.getLogger("ak_news.telegram_ingestion")


class TelegramIngestionService:
    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self._running: bool = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def is_connected(self) -> bool:
        return bool(self.client and self.client.is_connected())

    async def start(self) -> bool:
        if self._running and self.is_connected():
            return True

        api_id = settings.TELEGRAM_API_ID
        api_hash = settings.TELEGRAM_API_HASH
        if not api_id or not api_hash:
            logger.info("Telegram API ID or Hash not configured; skipping MTProto ingestion service.")
            return False

        session_path = str(settings.data_dir / "telegram_session")
        try:
            self.client = TelegramClient(session_path, int(api_id), api_hash)
            await self.client.connect()

            if not await self.client.is_user_authorized():
                logger.info("Telegram client is not logged in; use /settings/telegram to authorize.")
                return False

            self._running = True
            logger.info("Telegram MTProto live ingestion service connected successfully!")

            # Register message handler
            @self.client.on(events.NewMessage())
            async def _message_handler(event):
                await self._process_incoming_event(event)

            # Run catch-up in background
            asyncio.create_task(self.catch_up_missed_messages())
            return True
        except Exception as e:
            logger.error(f"Failed to start Telegram ingestion service: {e}")
            self._running = False
            return False

    async def stop(self) -> None:
        self._running = False
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass
            self.client = None
        logger.info("Telegram MTProto ingestion service stopped.")

    async def _process_incoming_event(self, event) -> None:
        try:
            chat = await event.get_chat()
            chat_id = getattr(chat, "id", None)
            chat_username = getattr(chat, "username", None)
            if not chat_id:
                return

            db: Session = SessionLocal()
            try:
                # Find matching active source channel
                q = db.query(SourceChannel).filter(SourceChannel.is_active == True)
                matched_source = None
                if chat_username:
                    uname = chat_username.lstrip("@")
                    matched_source = q.filter((SourceChannel.username == uname) | (SourceChannel.username == f"@{uname}")).first()
                if not matched_source and chat_id:
                    try:
                        cid = int(chat_id)
                        matched_source = q.filter(SourceChannel.telegram_channel_id == cid).first()
                    except (ValueError, TypeError):
                        pass

                if not matched_source:
                    return

                msg_id = event.message.id
                # Check duplicate message ID
                existing = (
                    db.query(RawPost)
                    .filter(RawPost.source_id == matched_source.id, RawPost.telegram_message_id == msg_id)
                    .first()
                )
                if existing:
                    return

                text = event.message.message or ""
                text_hash = compute_text_hash(text) if text else None

                is_dup = False
                if text:
                    norm = normalize_post_text(text)
                    is_dup, _ = check_deduplication(db, norm)

                post = RawPost(
                    source_id=matched_source.id,
                    telegram_message_id=msg_id,
                    cleaned_text=text,
                    text_hash=text_hash,
                    source_url=f"https://t.me/{chat_username}/{msg_id}" if chat_username else "",
                    status=RawPostStatus.DUPLICATE.value if is_dup else RawPostStatus.NEW.value,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(post)
                db.flush()

                # Handle media download
                if event.message.media and source_quota_allows(db, matched_source.id):
                    try:
                        ext = ".jpg"
                        media_type = MediaType.PHOTO.value
                        if isinstance(event.message.media, MessageMediaDocument):
                            ext = ".mp4" if "video" in getattr(event.message.media.document, "mime_type", "") else ".bin"
                            media_type = MediaType.VIDEO.value if ext == ".mp4" else MediaType.PHOTO.value

                        target_path = prepare_media_target_path(post.id, f"media_1{ext}")
                        downloaded = await event.message.download_media(file=str(target_path))
                        if downloaded and target_path.exists():
                            m_item = MediaItem(
                                post_id=post.id,
                                media_type=media_type,
                                local_path=str(target_path),
                                file_size=target_path.stat().st_size,
                            )
                            db.add(m_item)
                            add_source_usage(db, matched_source.id, target_path.stat().st_size)
                    except Exception as me:
                        logger.warning(f"Failed to download media for post #{post.id}: {me}")

                db.commit()

                if not is_dup:
                    queue_post_notifications(post)

            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error handling Telegram event: {e}")

    async def catch_up_missed_messages(self, limit_per_channel: int = 20) -> None:
        if not self.is_connected():
            return
        logger.info("Running catch-up for Telegram channels...")
        db: Session = SessionLocal()
        try:
            channels = (
                db.query(SourceChannel)
                .filter(SourceChannel.source_type == "telegram", SourceChannel.is_active == True)
                .all()
            )
            for sc in channels:
                ident = sc.username or sc.telegram_channel_id
                if not ident:
                    continue
                try:
                    entity = await self.client.get_entity(ident)
                    messages = await self.client.get_messages(entity, limit=limit_per_channel)
                    for msg in messages:
                        # Process message silently if not stored
                        existing = (
                            db.query(RawPost.id)
                            .filter(RawPost.source_id == sc.id, RawPost.telegram_message_id == msg.id)
                            .first()
                        )
                        if not existing and (msg.message or msg.media):
                            text = msg.message or ""
                            post = RawPost(
                                source_id=sc.id,
                                telegram_message_id=msg.id,
                                cleaned_text=text,
                                text_hash=compute_text_hash(text) if text else None,
                                status=RawPostStatus.NEW.value,
                                created_at=msg.date or datetime.now(timezone.utc),
                            )
                            db.add(post)
                            db.commit()
                except Exception as ce:
                    logger.warning(f"Catch-up failed for source {ident}: {ce}")
        finally:
            db.close()
        logger.info("Catch-up scan completed.")


# Singleton service
ingestion_service = TelegramIngestionService()


def get_client() -> Optional[TelegramClient]:
    return ingestion_service.client
