import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import OutboxNotification, User, Role

logger = logging.getLogger("ak_news.staff_notify")

# Temporary in-memory token storage for linking Telegram chat IDs to Staff user accounts
# token -> {"user_id": int, "expires_at": datetime}
_LINK_TOKENS: Dict[str, Dict] = {}


def create_link_token(user_id: int, valid_minutes: int = 30) -> str:
    token = uuid.uuid4().hex[:12].upper()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=valid_minutes)
    _LINK_TOKENS[token] = {
        "user_id": user_id,
        "expires_at": expires_at
    }
    return token


def consume_link_token(token: str) -> Optional[int]:
    item = _LINK_TOKENS.pop(token.strip().upper(), None)
    if not item:
        return None
    if datetime.now(timezone.utc) > item["expires_at"]:
        return None
    return item["user_id"]


def link_telegram_account(user_id: int, telegram_chat_id: int) -> bool:
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.telegram_id = telegram_chat_id
            db.commit()
            logger.info(f"User #{user_id} ({user.username}) linked to Telegram chat ID: {telegram_chat_id}")
            return True
        return False
    finally:
        db.close()


async def notify_user(user: User, text: str) -> bool:
    if not user.telegram_id:
        return False
    db: Session = SessionLocal()
    try:
        notif = OutboxNotification(
            target_chat_id=user.telegram_id,
            text=text,
            status="pending",
            created_at=datetime.now(timezone.utc)
        )
        db.add(notif)
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to queue notification for user #{user.id}: {e}")
        return False
    finally:
        db.close()


def notify_all_staff(text: str, role: Optional[str] = None) -> int:
    db: Session = SessionLocal()
    count = 0
    try:
        q = db.query(User).join(User.role).filter(User.telegram_id.isnot(None), User.is_active == True)
        if role:
            q = q.filter((Role.slug == role) | (Role.name == role))
        users = q.all()

        for u in users:
            notif = OutboxNotification(
                target_chat_id=u.telegram_id,
                text=text,
                status="pending",
                created_at=datetime.now(timezone.utc)
            )
            db.add(notif)
            count += 1
        db.commit()
    except Exception as e:
        logger.error(f"Failed to notify staff: {e}")
    finally:
        db.close()
    return count
