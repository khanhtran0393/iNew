from datetime import datetime, timezone
from typing import Optional
from app.database import SessionLocal
from app.models import RawPost, WorkflowStatus, WorkflowAuditLog, User


def claim_post_atomic(post_id: int, user_id: int) -> bool:
    db = SessionLocal()
    try:
        post = db.query(RawPost).filter_by(id=post_id).first()
        if not post:
            return False
        post.assigned_to = user_id
        post.workflow_status = WorkflowStatus.EDITING.value
        log = WorkflowAuditLog(
            raw_post_id=post.id,
            user_id=user_id,
            action="claim",
            to_status=WorkflowStatus.EDITING.value
        )
        db.add(log)
        db.commit()
        return True
    finally:
        db.close()


def update_post_status(post_id: int, new_status: str, user_id: Optional[int] = None, note: str = "") -> bool:
    db = SessionLocal()
    try:
        post = db.query(RawPost).filter_by(id=post_id).first()
        if not post:
            return False
        old_status = post.workflow_status
        post.workflow_status = new_status
        log = WorkflowAuditLog(
            raw_post_id=post.id,
            user_id=user_id,
            action="update_status",
            from_status=old_status,
            to_status=new_status,
            note=note
        )
        db.add(log)
        db.commit()
        return True
    finally:
        db.close()
