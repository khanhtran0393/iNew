"""Editorial workflow transitions, auditing and post assignments."""

from typing import Optional
from sqlalchemy.orm import Session
from app.models import RawPost, WorkflowStatus, WorkflowAuditLog, _utcnow


def transition_post_workflow(
    db: Session,
    post: RawPost,
    to_status: WorkflowStatus,
    user_id: Optional[int] = None,
    notes: str = ""
) -> bool:
    from_status = post.workflow_status
    post.workflow_status = to_status.value
    audit = WorkflowAuditLog(
        raw_post_id=post.id,
        user_id=user_id,
        action="transition",
        from_status=from_status,
        to_status=to_status.value,
        notes=notes,
        created_at=_utcnow()
    )
    db.add(audit)
    db.commit()
    return True
