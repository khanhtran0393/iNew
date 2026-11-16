from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import User, RoleSlug
from app.web.templating import templates
from app.web.auth import get_current_user_optional, user_is_admin
from app.services.licensing import (
    evaluate_state, machine_fingerprint, license_server_url,
    save_installed_token, activate_online
)

router = APIRouter(prefix="/license", tags=["license"])


def _is_admin(request: Request, db: Session) -> bool:
    user = get_current_user_optional(request, db)
    return user_is_admin(user)


@router.get("")
def license_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    state = evaluate_state()
    fp = machine_fingerprint()
    has_srv = bool(license_server_url())

    return templates.TemplateResponse("license.html", {
        "request": request,
        "current_user": user,
        "state": state,
        "fingerprint": fp,
        "has_server": has_srv,
        "app_version": settings.VERSION,
        "key_bot": settings.KEY_BOT_USERNAME or "iNewKeyBot"
    })


@router.post("/install")
def license_install(request: Request, token: str = Form(...), db: Session = Depends(get_db)):
    if not _is_admin(request, db):
        return RedirectResponse(url="/license?err=admin", status_code=303)
    save_installed_token(token)
    return RedirectResponse(url="/license?ok=Cài+đặt+thành+công", status_code=303)


@router.post("/activate")
async def license_activate(request: Request, activation_code: str = Form(...), db: Session = Depends(get_db)):
    if not _is_admin(request, db):
        return RedirectResponse(url="/license?err=admin", status_code=303)
    res = await activate_online(activation_code)
    if res.get("ok"):
        return RedirectResponse(url="/license?ok=Kích+hoạt+online+thành+công", status_code=303)
    return RedirectResponse(url=f"/license?err={res.get('error')}", status_code=303)
