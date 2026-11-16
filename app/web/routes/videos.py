from typing import Optional
from fastapi import APIRouter, Request, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import GeneratedVideo, MediaItem, SourceChannel, User
from app.web.templating import templates
from app.web.auth import get_current_user

router = APIRouter(prefix="/videos", tags=["videos"])


@router.get("")
def videos_view(
    request: Request,
    tab: str = Query("generated"),
    media: str = Query("all"),
    state: str = Query("all"),
    source_id: Optional[str] = Query(None),
    page: int = Query(1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sources = db.query(SourceChannel).filter(SourceChannel.is_active == True).all()

    items = []
    generated = []
    total_count = 0

    if tab == "source":
        q = db.query(MediaItem)
        if media != "all":
            q = q.filter(MediaItem.media_type == media)
        total_count = q.count()
        items = q.order_by(MediaItem.id.desc()).limit(60).all()
    else:
        q = db.query(GeneratedVideo)
        if state != "all":
            q = q.filter(GeneratedVideo.status == state)
        total_count = q.count()
        generated = q.order_by(GeneratedVideo.id.desc()).limit(60).all()

    can_edit = bool(user and (user.role in ("admin", "lead", "editor") or getattr(user.role, "slug", "") in ("admin", "lead", "editor")))

    return templates.TemplateResponse(
        "videos.html",
        {
            "request": request,
            "current_user": user,
            "tab": tab,
            "media": media,
            "state": state,
            "source_id": int(source_id) if source_id and source_id.isdigit() else None,
            "page": page,
            "total_pages": 1,
            "current_page": page,
            "total": total_count,
            "has_next": False,
            "can_edit": can_edit,
            "pending_marker": "pending",
            "items": items,
            "generated": generated,
            "videos": items if tab == "source" else generated,
            "sources": sources,
        }
    )
