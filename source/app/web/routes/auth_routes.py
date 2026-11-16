"""Authentication routes (login, logout, change password)."""

from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.init_db import verify_password, hash_password
from app.web.auth import (
    COOKIE_NAME, create_session_token, get_current_user,
    record_login_failure, clear_login_failures, login_is_locked
)
from app.web.templating import templates

router = APIRouter(tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    ip = request.client.host if request.client else "unknown"
    if login_is_locked(ip):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Tài khoản tạm thời bị khóa do nhập sai nhiều lần. Vui lòng thử lại sau 15 phút."}, status_code=400)

    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if not user or not verify_password(user.password_hash, password):
        record_login_failure(ip)
        return templates.TemplateResponse("login.html", {"request": request, "error": "Sai tên đăng nhập hoặc mật khẩu."}, status_code=400)

    clear_login_failures(ip)
    token = create_session_token(user.id)
    resp = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    resp.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax")
    return resp


@router.get("/logout")
async def logout(request: Request):
    resp = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    resp.delete_cookie(COOKIE_NAME)
    return resp


@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("change_password.html", {"request": request, "user": user, "error": None, "success": None})


@router.post("/change-password")
async def change_password_submit(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(user.password_hash, old_password):
        return templates.TemplateResponse("change_password.html", {"request": request, "user": user, "error": "Mật khẩu cũ không chính xác.", "success": None}, status_code=400)
    user.password_hash = hash_password(new_password)
    db.commit()
    return templates.TemplateResponse("change_password.html", {"request": request, "user": user, "error": None, "success": "Đổi mật khẩu thành công!"})
