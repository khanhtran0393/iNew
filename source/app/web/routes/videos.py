"""Video rendering and video editor routes."""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, GeneratedVideo
from app.web.auth import get_current_user
from app.web.templating import templates

router = APIRouter(prefix="/videos", tags=["videos"])


@router.get("", response_class=HTMLResponse)
async def videos_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    videos = db.query(GeneratedVideo).order_by(GeneratedVideo.id.desc()).all()
    return templates.TemplateResponse("videos.html", {"request": request, "user": user, "videos": videos})


@router.get("/editor", response_class=HTMLResponse)
async def video_editor_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("video_editor.html", {"request": request, "user": user})
