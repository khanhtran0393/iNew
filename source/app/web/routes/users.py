"""User accounts and staff management routes."""

from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Role, _utcnow
from app.init_db import hash_password
from app.web.auth import require_admin
from app.web.templating import templates

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_class=HTMLResponse)
async def users_page(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).all()
    roles = db.query(Role).all()
    return templates.TemplateResponse("users.html", {"request": request, "user": user, "users": users, "roles": roles})


@router.post("/add")
async def add_user(
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(""),
    role_id: str = Form("editor"),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    new_user = User(
        username=username,
        password_hash=hash_password(password),
        full_name=full_name,
        role_id=role_id,
        is_active=True,
        created_at=_utcnow()
    )
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/users", status_code=status.HTTP_302_FOUND)
