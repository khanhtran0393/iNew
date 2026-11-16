"""Dashboard overview and main statistics page."""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, RawPost, SourceChannel, Topic
from app.web.auth import get_current_user
from app.web.templating import templates

router = APIRouter(tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total_posts = db.query(RawPost).count()
    pending_posts = db.query(RawPost).filter(RawPost.workflow_status == "claimed").count()
    completed_posts = db.query(RawPost).filter(RawPost.workflow_status == "completed").count()
    channels_count = db.query(SourceChannel).filter(SourceChannel.is_deleted == False).count()
    recent_posts = db.query(RawPost).order_by(RawPost.id.desc()).limit(10).all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "stats": {
            "total_posts": total_posts,
            "pending_posts": pending_posts,
            "completed_posts": completed_posts,
            "channels_count": channels_count,
        },
        "recent_posts": recent_posts
    })
