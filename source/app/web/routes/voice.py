"""TTS Voice Studio and profiles management."""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, VoiceProfile
from app.web.auth import get_current_user
from app.web.templating import templates
from app.services.voice_studio import list_available_voices

router = APIRouter(prefix="/voice", tags=["voice"])


@router.get("", response_class=HTMLResponse)
async def voice_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profiles = db.query(VoiceProfile).all()
    voices = list_available_voices()
    return templates.TemplateResponse("voice.html", {
        "request": request,
        "user": user,
        "profiles": profiles,
        "available_voices": voices
    })
