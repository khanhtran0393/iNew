"""System, Telegram, and AI settings configuration routes."""

from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, AppSetting, AiApiKey, _utcnow
from app.web.auth import require_admin
from app.web.templating import templates
from app.config import settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/ai", response_class=HTMLResponse)
async def settings_ai_page(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    keys = db.query(AiApiKey).all()
    return templates.TemplateResponse("settings_ai.html", {"request": request, "user": user, "keys": keys, "settings": settings})


@router.get("/telegram", response_class=HTMLResponse)
async def settings_telegram_page(request: Request, user: User = Depends(require_admin)):
    return templates.TemplateResponse("telegram_settings.html", {"request": request, "user": user, "settings": settings})


@router.get("/system", response_class=HTMLResponse)
async def settings_system_page(request: Request, user: User = Depends(require_admin)):
    return templates.TemplateResponse("system_settings.html", {"request": request, "user": user, "settings": settings})
