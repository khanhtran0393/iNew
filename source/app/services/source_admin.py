"""Source channel management and moderation."""

from typing import Optional, List
from app.database import SessionLocal
from app.models import SourceChannel, _utcnow


def list_sources(include_deleted: bool = False) -> List[SourceChannel]:
    db = SessionLocal()
    try:
        q = db.query(SourceChannel)
        if not include_deleted:
            q = q.filter(SourceChannel.is_deleted == False)
        return q.order_by(SourceChannel.created_at.desc()).all()
    finally:
        db.close()


def soft_delete_source(source_id: int) -> bool:
    db = SessionLocal()
    try:
        src = db.query(SourceChannel).filter(SourceChannel.id == source_id).first()
        if src:
            src.is_deleted = True
            src.deleted_at = _utcnow()
            db.commit()
            return True
        return False
    finally:
        db.close()
