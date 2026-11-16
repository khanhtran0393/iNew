from typing import Optional
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Role
from app.web.templating import templates
from app.web.auth import get_current_user, require_roles, hash_password, verify_password

router = APIRouter(prefix="", tags=["users"])


@router.get("/users")
def users_view(
    request: Request,
    notice: str = "",
    user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    users = db.query(User).order_by(User.id.asc()).all()
    return templates.TemplateResponse(
        "users.html",
        {
            "request": request,
            "current_user": user,
            "users": users,
            "roles": [r.value for r in Role] if hasattr(Role, "__iter__") else ["admin", "lead", "editor", "viewer"],
            "notice": notice,
        }
    )


@router.get("/users/change-password")
@router.get("/change-password")
def change_password_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("change_password.html", {"request": request, "current_user": user})


@router.post("/users/create")
def create_user(
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(""),
    role: str = Form("editor"),
    user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    u_clean = username.strip().lower()
    existing = db.query(User).filter(User.username == u_clean).first()
    if not existing and u_clean and password:
        new_u = User(
            username=u_clean,
            password_hash=hash_password(password),
            full_name=full_name.strip() or u_clean,
            role=role,
            is_active=True
        )
        db.add(new_u)
        db.commit()
    return RedirectResponse(url="/users", status_code=303)


@router.post("/users/toggle/{user_id}")
@router.post("/users/{user_id}/toggle")
def toggle_user(
    user_id: int,
    user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    target = db.query(User).filter(User.id == user_id).first()
    if target and target.id != user.id:
        target.is_active = not target.is_active
        db.commit()
    return RedirectResponse(url="/users", status_code=303)


@router.post("/users/reset_password/{user_id}")
@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    new_password: str = Form(...),
    user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    target = db.query(User).filter(User.id == user_id).first()
    if target and new_password:
        target.password_hash = hash_password(new_password)
        db.commit()
    return RedirectResponse(url="/users", status_code=303)


@router.post("/users/me/password")
def change_own_password(
    old_password: str = Form(...),
    new_password: str = Form(...),
    new_password_confirm: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if new_password != new_password_confirm:
        return RedirectResponse(url="/change-password?err=M%E1%BA%ADt+kh%E1%BA%A9u+nh%E1%BA%ADp+l%E1%BA%A1i+kh%C3%B4ng+kh%E1%BB%9Bp", status_code=303)
    if not verify_password(old_password, user.password_hash):
        return RedirectResponse(url="/change-password?err=M%E1%BA%ADt+kh%E1%BA%A9u+c%C5%A9+kh%C3%B4ng+%C4%91%C3%BAng", status_code=303)

    user.password_hash = hash_password(new_password)
    db.commit()
    return RedirectResponse(url="/change-password?ok=%C4%90%E1%BB%95i+m%E1%BA%ADt+kh%E1%BA%A9u+th%C3%A0nh+c%C3%B4ng", status_code=303)


@router.post("/users/me/telegram-link")
def link_own_telegram(
    telegram_user_id: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user.telegram_user_id = telegram_user_id.strip()
    db.commit()
    return RedirectResponse(url="/change-password?ok=%C4%90%C3%A3+li%C3%AAn+k%E1%BA%BFt+Telegram", status_code=303)


@router.post("/users/me/telegram-unlink")
def unlink_own_telegram(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user.telegram_user_id = None
    db.commit()
    return RedirectResponse(url="/change-password?ok=%C4%90%C3%A3+h%E1%BB%A7y+li%C3%AAn+k%E1%BA%BFt+Telegram", status_code=303)
