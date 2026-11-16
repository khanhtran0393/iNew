import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import SourceChannel

logger = logging.getLogger("ak_news.source_admin")


def remove_source(source_id: int) -> bool:
    db: Session = SessionLocal()
    try:
        sc = db.query(SourceChannel).filter(SourceChannel.id == source_id).first()
        if sc:
            sc.is_active = False
            db.commit()
            logger.info(f"Source channel #{source_id} deactivated.")
            return True
        return False
    finally:
        db.close()


def restore_if_deleted(db: Session, source_id: int) -> bool:
    sc = db.query(SourceChannel).filter(SourceChannel.id == source_id).first()
    if sc and not sc.is_active:
        sc.is_active = True
        db.commit()
        logger.info(f"Source channel #{source_id} ({sc.title}) restored to active state.")
        return True
    return False


def toggle_source(db: Session, source_id: int) -> Optional[bool]:
    sc = db.query(SourceChannel).filter(SourceChannel.id == source_id).first()
    if sc:
        sc.is_active = not sc.is_active
        db.commit()
        logger.info(f"Source channel #{source_id} toggled to is_active={sc.is_active}")
        return sc.is_active
    return None


def set_source_priority(db: Session, source_id: int, priority: str) -> bool:
    sc = db.query(SourceChannel).filter(SourceChannel.id == source_id).first()
    if sc:
        sc.priority = priority.upper()
        db.commit()
        return True
    return False
