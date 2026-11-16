"""Web session authentication and role-based access control."""

import time
import hmac
import hashlib
from typing import Optional, List
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import User, Role

COOKIE_NAME = "ak_news_session"
_login_failures = {}


def create_session_token(user_id: int) -> str:
    timestamp = int(time.time())
    payload = f"{user_id}:{timestamp}"
    sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def verify_session_token(token: str) -> Optional[int]:
    if not token or ":" not in token:
        return None
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return None
        user_id_str, ts_str, sig = parts
        payload = f"{user_id_str}:{ts_str}"
        expected_sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        return int(user_id_str)
    except Exception:
        return None


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    user_id = verify_session_token(token)
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user_optional(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập. Vui lòng đăng nhập để tiếp tục.")
    return user


def require_roles(allowed_slugs: List[str]):
    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role and user.role.slug in allowed_slugs:
            return user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền truy cập vào chức năng này.")
    return role_checker


require_admin = require_roles(["admin"])
require_lead = require_roles(["admin", "lead"])
require_editor = require_roles(["admin", "lead", "editor"])
require_staff = require_roles(["admin", "lead", "editor", "monitor"])


def user_is_admin(user: User) -> bool:
    return bool(user.role and user.role.slug == "admin")


def user_can_edit(user: User) -> bool:
    return bool(user.role and user.role.slug in ("admin", "lead", "editor"))


def login_is_locked(key: str) -> bool:
    now = time.time()
    attempts = [t for t in _login_failures.get(key, []) if now - t < settings.LOGIN_LOCKOUT_MINUTES * 60]
    _login_failures[key] = attempts
    return len(attempts) >= settings.LOGIN_MAX_FAILURES


def record_login_failure(key: str):
    _login_failures.setdefault(key, []).append(time.time())


def clear_login_failures(key: str):
    _login_failures.pop(key, None)
