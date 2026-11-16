from fastapi import APIRouter, Request, Form, Depends, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.init_db import verify_password
from app.web.templating import templates
from app.web.auth import create_session_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login_submit(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter_by(username=username.strip()).first()
    if not user or not verify_password(user.password_hash, password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Sai tài khoản hoặc mật khẩu."})

    token = create_session_token(user.id)
    resp = RedirectResponse(url="/dashboard", status_code=303)
    resp.set_cookie("inew_session", token, httponly=True, max_age=86400 * 7)
    return resp


@router.get("/logout")
def logout(response: Response):
    resp = RedirectResponse(url="/auth/login", status_code=303)
    resp.delete_cookie("inew_session")
    return resp
