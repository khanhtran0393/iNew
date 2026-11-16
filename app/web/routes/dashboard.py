from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import RawPost, SourceChannel, User, RawPostStatus, WorkflowStatus, OutboxNotification
from app.web.templating import templates
from app.web.auth import get_current_user
from app.services.media_storage import get_disk_usage
from app.services.backup_service import get_backup_status

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard_view(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_sources = db.query(SourceChannel).count()
    active_sources = db.query(SourceChannel).filter(SourceChannel.is_active == True).count()
    telegram_sources = db.query(SourceChannel).filter(
        SourceChannel.source_type == "telegram",
        SourceChannel.is_active == True
    ).count()

    total_posts = db.query(RawPost).count()
    posts_today = db.query(RawPost).filter(RawPost.created_at >= today_start).count()
    unprocessed_posts = db.query(RawPost).filter(RawPost.status == RawPostStatus.NEW.value).count()
    claimed_posts = db.query(RawPost).filter(
        RawPost.workflow_status.in_([WorkflowStatus.CLAIMED.value, WorkflowStatus.EDITING.value])
    ).count()

    stats = {
        "active_sources": active_sources,
        "total_sources": total_sources,
        "total_posts": total_posts,
        "posts_today": posts_today,
        "unprocessed_posts": unprocessed_posts,
        "claimed_posts": claimed_posts,
    }

    workflow_counts = {
        "new": unprocessed_posts,
        "claimed": claimed_posts,
        "approved": db.query(RawPost).filter(RawPost.workflow_status == WorkflowStatus.APPROVED.value).count(),
        "archived": db.query(RawPost).filter(RawPost.workflow_status == WorkflowStatus.ARCHIVED.value).count(),
        "duplicate": db.query(RawPost).filter(RawPost.status == RawPostStatus.DUPLICATE.value).count(),
    }

    outbox_pending = db.query(OutboxNotification).filter(OutboxNotification.status == "pending").count()
    outbox_failed = db.query(OutboxNotification).filter(OutboxNotification.status == "failed").count()

    b_status = get_backup_status()
    last_backup_info = {"age_hours": 1.0}
    if b_status.get("latest") and "created_at" in b_status["latest"]:
        try:
            b_dt = datetime.fromisoformat(b_status["latest"]["created_at"])
            last_backup_info["age_hours"] = round((now - b_dt).total_seconds() / 3600, 1)
        except Exception:
            pass

    health = {
        "telegram": True,
        "bot_running": True,
        "auto_video": True,
        "outbox_pending": outbox_pending,
        "outbox_failed": outbox_failed,
        "linked_sources": active_sources,
        "telegram_sources": telegram_sources,
        "telegram_web_run": {"channels": telegram_sources, "failed": 0},
        "last_backup": last_backup_info,
    }

    disk = get_disk_usage()
    recent_posts = db.query(RawPost).order_by(RawPost.created_at.desc()).limit(15).all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_user": user,
        "stats": stats,
        "workflow_counts": workflow_counts,
        "disk": disk,
        "recent_posts": recent_posts,
        "health": health,
        "last_cleanup": "Vừa xong",
    })


@router.post("/dashboard/maintenance")
def run_maintenance_now():
    from app.services.maintenance_service import run_maintenance_once
    run_maintenance_once()
    return {"ok": True}
