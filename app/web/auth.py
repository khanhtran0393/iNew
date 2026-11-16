import json
import base64
import hashlib
from typing import Optional, List
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db, SessionLocal
from app.models import User, RoleSlug
from app.init_db import hash_password, verify_password


def create_session_token(user_id: int) -> str:
    payload = json.dumps({"uid": user_id}).encode("utf-8")
    sig = hashlib.sha256(payload + settings.SECRET_KEY.encode("utf-8")).hexdigest()
    return f"{base64.urlsafe_b64encode(payload).decode('utf-8')}.{sig}"


def verify_session_token(token: str) -> Optional[int]:
    if not token or "." not in token:
        return None
    try:
        p_b64, sig = token.split(".", 1)
        payload = base64.urlsafe_b64decode(p_b64.encode("utf-8"))
        expected_sig = hashlib.sha256(payload + settings.SECRET_KEY.encode("utf-8")).hexdigest()
        if sig != expected_sig:
            return None
        data = json.loads(payload.decode("utf-8"))
        return data.get("uid")
    except Exception:
        return None


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    token = request.cookies.get("inew_session")
    uid = verify_session_token(token)
    if not uid:
        return None
    return db.query(User).filter(User.id == uid, User.is_active == True).first()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user_optional(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Vui lòng đăng nhập")
    return user


def require_roles(allowed_slugs: List[str]):
    def checker(user: User = Depends(get_current_user)) -> User:
        slug = ""
        if hasattr(user, "role") and user.role:
            slug = getattr(user.role, "slug", "") or str(user.role)
        if slug not in allowed_slugs:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập")
        return user
    return checker


def require_editor(user: User = Depends(get_current_user)) -> User:
    slug = ""
    if hasattr(user, "role") and user.role:
        slug = getattr(user.role, "slug", "") or str(user.role)
    if slug not in ("admin", "lead", "editor"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền biên tập")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    slug = ""
    if hasattr(user, "role") and user.role:
        slug = getattr(user.role, "slug", "") or str(user.role)
    if slug != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Yêu cầu quyền Quản trị viên (Admin)")
    return user


def user_is_admin(user: User) -> bool:
    if not user:
        return False
    slug = ""
    if hasattr(user, "role") and user.role:
        slug = getattr(user.role, "slug", "") or str(user.role)
    return slug == "admin"


def set_session_cookie(response, user):
    token = create_session_token(user.id)
    response.set_cookie("inew_session", token, httponly=True, max_age=86400 * 7)
