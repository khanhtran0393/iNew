"""Topic categorization and editorial groups management."""

from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Topic, _utcnow
from app.web.auth import require_admin
from app.web.templating import templates

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("", response_class=HTMLResponse)
async def topics_page(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    topics = db.query(Topic).all()
    return templates.TemplateResponse("topics.html", {"request": request, "user": user, "topics": topics})


@router.post("/add")
async def add_topic(
    name: str = Form(...),
    description: str = Form(""),
    color: str = Form("#3b82f6"),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    t = Topic(name=name, description=description, color=color, created_at=_utcnow())
    db.add(t)
    db.commit()
    return RedirectResponse(url="/topics", status_code=status.HTTP_302_FOUND)
