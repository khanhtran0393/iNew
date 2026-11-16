import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import SourceChannel, RawPost, User
from app.web.templating import templates
from app.web.auth import get_current_user, require_admin
from app.services.bulk_import import bulk_import_channels
from app.services.source_admin import remove_source, toggle_source
from app.services.rss_collector import sync_all_rss_sources

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("")
def sources_view(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sources = db.query(SourceChannel).order_by(SourceChannel.id.asc()).all()

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    post_counts = {}
    for s in sources:
        total = db.query(func.count(RawPost.id)).filter(RawPost.source_id == s.id).scalar() or 0
        today = db.query(func.count(RawPost.id)).filter(RawPost.source_id == s.id, RawPost.created_at >= today_start).scalar() or 0
        post_counts[s.id] = (total, today)

    return templates.TemplateResponse("sources.html", {
        "request": request,
        "current_user": user,
        "sources": sources,
        "post_counts": post_counts,
        "import_result": None,
    })


@router.post("/toggle/{source_id}")
@router.post("/{source_id}/toggle")
def toggle_source_endpoint(source_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    toggle_source(db, source_id)
    return RedirectResponse(url="/sources", status_code=303)


@router.post("/delete/{source_id}")
@router.post("/{source_id}/delete")
def delete_source_endpoint(source_id: int, user: User = Depends(get_current_user)):
    remove_source(source_id)
    return RedirectResponse(url="/sources", status_code=303)


@router.post("/{source_id}/quota")
def update_source_quota(source_id: int, quota_mb: int = Form(1024), user: User = Depends(require_admin), db: Session = Depends(get_db)):
    s = db.query(SourceChannel).filter_by(id=source_id).first()
    if s:
        s.storage_quota_mb = max(100, quota_mb)
        db.commit()
    return RedirectResponse(url="/sources", status_code=303)


@router.post("/bulk_import")
@router.post("/bulk-import")
def bulk_import_submit(
    channels_text: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    lines = channels_text.splitlines()
    bulk_import_channels(db, lines)
    return RedirectResponse(url="/sources", status_code=303)


@router.post("/sync-rss")
async def sync_rss_endpoint(user: User = Depends(get_current_user)):
    await asyncio.to_thread(sync_all_rss_sources)
    return RedirectResponse(url="/sources", status_code=303)
