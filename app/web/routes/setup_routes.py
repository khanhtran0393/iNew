import os
from typing import Optional
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, SessionLocal
from app.models import User, AppSetting, Role
from app.web.templating import templates
from app.web.auth import hash_password, set_session_cookie, get_current_user
from app.services.runtime_config import setup_completed, mark_setup_completed
from app.telegram_login import send_code_request, verify_login_code

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("")
def setup_page(request: Request, db: Session = Depends(get_db)):
    if setup_completed():
        return RedirectResponse(url="/dashboard", status_code=303)

    admin = db.query(User).filter(User.role.has(slug="admin")).first()
    api_id_row = db.query(AppSetting).filter_by(key="telegram_api_id").first()
    api_hash_row = db.query(AppSetting).filter_by(key="telegram_api_hash").first()
    bot_row = db.query(AppSetting).filter_by(key="telegram_bot_token").first()
    base_url_row = db.query(AppSetting).filter_by(key="public_base_url").first()

    api_id = api_id_row.value if api_id_row else (settings.TELEGRAM_API_ID or "")
    api_configured = bool(api_id and (api_hash_row or settings.TELEGRAM_API_HASH))
    bot_configured = bool(bot_row or settings.TELEGRAM_BOT_TOKEN)

    from app.services.telegram_ingestion import ingestion_service
    tg_state = "running" if ingestion_service.is_connected() else "not_authorized"

    return templates.TemplateResponse("setup.html", {
        "request": request,
        "admin": admin,
        "api_id": api_id,
        "api_configured": api_configured,
        "tg_state": tg_state,
        "bot_configured": bot_configured,
        "public_base_url": base_url_row.value if base_url_row else "",
        "code_sent": False,
        "awaiting_password": False,
    })


@router.post("/admin")
def setup_admin(
    full_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
    db: Session = Depends(get_db)
):
    if password != password2:
        return RedirectResponse(url="/setup?err=M%E1%BA%ADt+kh%E1%BA%A9u+nh%E1%BA%ADp+l%E1%BA%A1i+kh%C3%B4ng+kh%E1%BB%9Bp", status_code=303)

    existing = db.query(User).filter_by(username=username).first()
    if existing:
        return RedirectResponse(url="/setup?err=T%C3%AAn+%C4%91%C4%83ng+nh%E1%BA%ADp+%C4%91%C3%A3+t%E1%BB%93n+t%E1%BA%A1i", status_code=303)

    admin_role = db.query(Role).filter_by(slug="admin").first()
    user = User(
        username=username.strip(),
        full_name=full_name.strip(),
        password_hash=hash_password(password),
        role_id=admin_role.id if admin_role else 1,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    resp = RedirectResponse(url="/setup?ok=%C4%90%C3%A3+t%E1%BA%A1o+t%C3%A0i+kho%E1%BA%A3n+qu%E1%BA%A3n+tr%E1%BB%8B+th%C3%A0nh+c%C3%B4ng", status_code=303)
    set_session_cookie(resp, user)
    return resp


@router.post("/telegram-api")
def setup_telegram_api(
    api_id: str = Form(...),
    api_hash: str = Form(...),
    next: str = Form("/setup"),
    db: Session = Depends(get_db)
):
    for key, val in [("telegram_api_id", api_id.strip()), ("telegram_api_hash", api_hash.strip())]:
        row = db.query(AppSetting).filter_by(key=key).first()
        if not row:
            db.add(AppSetting(key=key, value=val))
        else:
            row.value = val
    db.commit()
    settings.TELEGRAM_API_ID = api_id.strip()
    settings.TELEGRAM_API_HASH = api_hash.strip()
    return RedirectResponse(url=f"{next}?ok=%C4%90%C3%A3+l%C6%B0u+c%E1%BA%A5u+h%C3%ACnh+API+Telegram", status_code=303)


@router.post("/telegram-code")
async def setup_telegram_code(
    phone: str = Form(...),
    db: Session = Depends(get_db)
):
    api_id_row = db.query(AppSetting).filter_by(key="telegram_api_id").first()
    api_hash_row = db.query(AppSetting).filter_by(key="telegram_api_hash").first()
    api_id = int(api_id_row.value) if api_id_row else int(settings.TELEGRAM_API_ID or 0)
    api_hash = api_hash_row.value if api_hash_row else (settings.TELEGRAM_API_HASH or "")

    if not api_id or not api_hash:
        return RedirectResponse(url="/setup?err=Ch%C6%B0a+c%E1%BA%A5u+h%C3%ACnh+API+ID+v%C3%A0+Hash", status_code=303)

    res = await send_code_request(phone, api_id, api_hash)
    if not res.get("ok"):
        return RedirectResponse(url=f"/setup?err={res.get('error', 'L%E1%BB%97i+g%E1%BB%ADi+m%C3%A3')}", status_code=303)
    return RedirectResponse(url="/setup?ok=%C4%90%C3%A3+g%E1%BB%ADi+m%C3%A3+Telegram", status_code=303)


@router.post("/telegram-login")
async def setup_telegram_login(
    code: str = Form(""),
    password: Optional[str] = Form(None)
):
    res = await verify_login_code(code, password)
    if not res.get("ok"):
        return RedirectResponse(url=f"/setup?err={res.get('error', '%C4%90%C4%83ng+nh%E1%BA%ADp+th%E1%BA%A5t+b%E1%BA%A1i')}", status_code=303)
    return RedirectResponse(url="/setup?ok=%C4%90%C4%83ng+nh%E1%BA%ADp+Telegram+th%C3%A0nh+c%C3%B4ng", status_code=303)


@router.post("/bot")
def setup_bot(
    bot_token: str = Form(...),
    public_base_url: Optional[str] = Form(""),
    next: str = Form("/setup"),
    db: Session = Depends(get_db)
):
    for key, val in [("telegram_bot_token", bot_token.strip()), ("public_base_url", (public_base_url or "").strip())]:
        row = db.query(AppSetting).filter_by(key=key).first()
        if not row:
            db.add(AppSetting(key=key, value=val))
        else:
            row.value = val
    db.commit()
    settings.TELEGRAM_BOT_TOKEN = bot_token.strip()
    return RedirectResponse(url=f"{next}?ok=%C4%90%C3%A3+k%E1%BA%BFt+n%E1%BB%91i+Bot+th%C3%A0nh+c%C3%B4ng", status_code=303)


@router.post("/finish")
def setup_finish():
    mark_setup_completed()
    return RedirectResponse(url="/dashboard", status_code=303)
