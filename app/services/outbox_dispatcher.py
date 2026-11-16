import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import OutboxNotification, RawPost, User
from app.services.telegram_bot import send_telegram_message

logger = logging.getLogger("ak_news.outbox_dispatcher")


def queue_post_notifications(
    post: RawPost,
    text: Optional[str] = None,
    target_chat_ids: Optional[List[int]] = None
) -> int:
    db: Session = SessionLocal()
    count = 0
    try:
        msg_text = text or f"🔔 [Tin Mới] {post.title or post.cleaned_text[:100]}"
        targets = target_chat_ids

        # If no explicit chat targets, notify all subscribed staff members
        if not targets:
            staff_users = db.query(User).filter(User.telegram_id.isnot(None), User.is_active == True).all()
            targets = [u.telegram_id for u in staff_users if u.telegram_id]

        for cid in targets:
            notif = OutboxNotification(
                target_chat_id=cid,
                raw_post_id=post.id,
                text=msg_text,
                status="pending",
                created_at=datetime.now(timezone.utc)
            )
            db.add(notif)
            count += 1
        db.commit()
    except Exception as e:
        logger.error(f"Failed to queue post notifications for post #{post.id}: {e}")
    finally:
        db.close()
    return count


async def dispatch_pending_outbox(batch_size: int = 20) -> int:
    db: Session = SessionLocal()
    sent_count = 0
    try:
        pending = (
            db.query(OutboxNotification)
            .filter(OutboxNotification.status == "pending")
            .order_by(OutboxNotification.created_at.asc())
            .limit(batch_size)
            .all()
        )

        for notif in pending:
            try:
                ok = await send_telegram_message(
                    chat_id=notif.target_chat_id,
                    text=notif.text
                )
                if ok:
                    notif.status = "sent"
                    notif.sent_at = datetime.now(timezone.utc)
                    sent_count += 1
                else:
                    notif.status = "failed"
                    notif.error_message = "Bot failed to send message."
            except Exception as e:
                notif.status = "failed"
                notif.error_message = str(e)
            db.commit()
    except Exception as e:
        logger.error(f"Error during outbox dispatch: {e}")
    finally:
        db.close()
    return sent_count


async def outbox_worker_loop(interval_seconds: int = 10):
    logger.info("Outbox notification worker loop started.")
    while True:
        try:
            await dispatch_pending_outbox()
        except Exception as e:
            logger.error(f"Outbox worker error: {e}")
        await asyncio.sleep(interval_seconds)
