"""Source channel administration routes."""

from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, SourceChannel, _utcnow
from app.web.auth import require_admin
from app.web.templating import templates

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_class=HTMLResponse)
async def sources_page(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    sources = db.query(SourceChannel).filter(SourceChannel.is_deleted == False).order_by(SourceChannel.created_at.desc()).all()
    return templates.TemplateResponse("sources.html", {"request": request, "user": user, "sources": sources})


@router.post("/add")
async def add_source(
    request: Request,
    title: str = Form(...),
    source_type: str = Form("telegram"),
    telegram_channel_id: int = Form(0),
    rss_url: str = Form(""),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    src = SourceChannel(
        title=title,
        source_type=source_type,
        telegram_channel_id=telegram_channel_id if source_type == "telegram" else None,
        rss_url=rss_url if source_type == "rss" else None,
        created_at=_utcnow()
    )
    db.add(src)
    db.commit()
    return RedirectResponse(url="/sources", status_code=status.HTTP_302_FOUND)
