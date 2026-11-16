"""License status and universal entitlement interface."""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.models import User
from app.web.auth import get_current_user_optional
from app.web.templating import templates
from app.services.licensing import evaluate_state, machine_fingerprint

router = APIRouter(prefix="/license", tags=["license"])


@router.get("", response_class=HTMLResponse)
async def license_page(request: Request, user: User = Depends(get_current_user_optional)):
    state = evaluate_state()
    fp = machine_fingerprint()
    return templates.TemplateResponse("license.html", {
        "request": request,
        "user": user,
        "state": state,
        "fingerprint": fp
    })
