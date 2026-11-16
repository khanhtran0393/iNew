import os
from pathlib import Path

web_dir = Path("app/web")
routes_dir = web_dir / "routes"
routes_dir.mkdir(parents=True, exist_ok=True)

(web_dir / "__init__.py").write_text('"""iNew Web Package."""\n', encoding="utf-8")
(routes_dir / "__init__.py").write_text('"""iNew Web Routes Package."""\n', encoding="utf-8")

# 1. app/web/templating.py
(web_dir / "templating.py").write_text('''from pathlib import Path
from fastapi.templating import Jinja2Templates

templates_dir = Path("app/web/templates")
templates = Jinja2Templates(directory=str(templates_dir))
''', encoding="utf-8")

# 2. app/web/auth.py
(web_dir / "auth.py").write_text('''import json
import base64
import hashlib
from typing import Optional, List
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db, SessionLocal
from app.models import User, RoleSlug
from app.init_db import verify_password


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
    return db.query(User).filter_by(id=uid, is_active=True).first()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user_optional(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Vui lòng đăng nhập")
    return user


def require_roles(allowed_slugs: List[str]):
    def checker(user: User = Depends(get_current_user)) -> User:
        if not user.role or user.role.slug not in allowed_slugs:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập")
        return user
    return checker


def user_is_admin(user: User) -> bool:
    return user and user.role and user.role.slug == RoleSlug.ADMIN.value
''', encoding="utf-8")

# 3. app/web/routes/auth_routes.py
(routes_dir / "auth_routes.py").write_text('''from fastapi import APIRouter, Request, Form, Depends, Response
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
''', encoding="utf-8")

# 4. app/web/routes/dashboard.py
(routes_dir / "dashboard.py").write_text('''from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import RawPost, SourceChannel, User
from app.web.templating import templates
from app.web.auth import get_current_user
from app.services.media_storage import get_disk_usage

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard_view(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total_posts = db.query(RawPost).count()
    total_sources = db.query(SourceChannel).filter_by(is_deleted=False).count()
    disk = get_disk_usage()
    recent_posts = db.query(RawPost).order_by(RawPost.created_at.desc()).limit(10).all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_user": user,
        "total_posts": total_posts,
        "total_sources": total_sources,
        "disk": disk,
        "recent_posts": recent_posts
    })


@router.post("/dashboard/maintenance")
def run_maintenance_now():
    from app.services.maintenance_service import run_maintenance_once
    run_maintenance_once()
    return {"ok": True}
''', encoding="utf-8")

# 5. app/web/routes/posts.py
(routes_dir / "posts.py").write_text('''from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import RawPost, User, WorkflowStatus
from app.web.templating import templates
from app.web.auth import get_current_user
from app.services.editorial_workflow import claim_post_atomic, update_post_status

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("")
def news_feed_view(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    posts = db.query(RawPost).order_by(RawPost.created_at.desc()).limit(50).all()
    return templates.TemplateResponse("feed.html", {
        "request": request,
        "current_user": user,
        "posts": posts
    })


@router.get("/{post_id}")
def post_detail_view(post_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.query(RawPost).filter_by(id=post_id).first()
    return templates.TemplateResponse("post_detail.html", {
        "request": request,
        "current_user": user,
        "post": post
    })


@router.post("/{post_id}/claim")
def claim_post_action(post_id: int, user: User = Depends(get_current_user)):
    claim_post_atomic(post_id, user.id)
    return RedirectResponse(url=f"/posts/{post_id}", status_code=303)


@router.post("/{post_id}/status")
def update_status_action(post_id: int, status: str = Form(...), user: User = Depends(get_current_user)):
    update_post_status(post_id, status, user_id=user.id)
    return RedirectResponse(url=f"/posts/{post_id}", status_code=303)


@router.post("/{post_id}/save")
def save_edited_text_action(post_id: int, edited_text: str = Form(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.query(RawPost).filter_by(id=post_id).first()
    if post:
        post.edited_text = edited_text
        db.commit()
    return RedirectResponse(url=f"/posts/{post_id}", status_code=303)
''', encoding="utf-8")

# 6. app/web/routes/license_routes.py
(routes_dir / "license_routes.py").write_text('''from fastapi import APIRouter, Request, Depends, Form
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
''', encoding="utf-8")

# 7. app/web/routes/sources.py
(routes_dir / "sources.py").write_text('''from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import SourceChannel, User
from app.web.templating import templates
from app.web.auth import get_current_user
from app.services.bulk_import import bulk_import_channels
from app.services.source_admin import remove_source

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("")
def sources_view(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sources = db.query(SourceChannel).filter_by(is_deleted=False).all()
    return templates.TemplateResponse("sources.html", {
        "request": request,
        "current_user": user,
        "sources": sources
    })


@router.post("/toggle/{source_id}")
def toggle_source(source_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sc = db.query(SourceChannel).filter_by(id=source_id).first()
    if sc:
        sc.is_active = not sc.is_active
        db.commit()
    return RedirectResponse(url="/sources", status_code=303)


@router.post("/delete/{source_id}")
def delete_source(source_id: int, user: User = Depends(get_current_user)):
    remove_source(source_id)
    return RedirectResponse(url="/sources", status_code=303)


@router.post("/bulk_import")
def bulk_import_submit(channels_text: str = Form(...), user: User = Depends(get_current_user)):
    lines = channels_text.splitlines()
    bulk_import_channels(lines)
    return RedirectResponse(url="/sources", status_code=303)
''', encoding="utf-8")

# 8. app/web/routes/settings_routes.py
(routes_dir / "settings_routes.py").write_text('''from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, AiApiKey
from app.web.templating import templates
from app.web.auth import get_current_user, user_is_admin

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/ai")
def ai_config_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    keys = db.query(AiApiKey).all()
    return templates.TemplateResponse("settings_ai.html", {
        "request": request,
        "current_user": user,
        "ai_keys": keys
    })


@router.get("/telegram")
def telegram_settings_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("telegram_settings.html", {
        "request": request,
        "current_user": user
    })
''', encoding="utf-8")

# 9. app/web/routes/api_routes.py
(routes_dir / "api_routes.py").write_text('''from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.web.auth import get_current_user
from app.services.ai_copilot import run_ai_action

router = APIRouter(prefix="/api", tags=["api"])


@router.post("/ai/action")
async def ai_action_endpoint(action: str, text: str, user: User = Depends(get_current_user)):
    res = await run_ai_action(action, text, user_id=user.id)
    return {"ok": True, "result": res}
''', encoding="utf-8")

# 10. app/web/routes/voice.py
(routes_dir / "voice.py").write_text('''from fastapi import APIRouter, Request, Depends
from app.web.templating import templates
from app.web.auth import get_current_user
from app.services.voice_studio import list_voices

router = APIRouter(prefix="/voice", tags=["voice"])


@router.get("")
def voice_studio_view(request: Request, user = Depends(get_current_user)):
    voices = list_voices()
    return templates.TemplateResponse("help.html", {"request": request, "current_user": user, "voices": voices})
''', encoding="utf-8")

# 11. app/web/routes/videos.py
(routes_dir / "videos.py").write_text('''from fastapi import APIRouter, Request, Depends
from app.web.templating import templates
from app.web.auth import get_current_user

router = APIRouter(prefix="/videos", tags=["videos"])


@router.get("")
def videos_view(request: Request, user = Depends(get_current_user)):
    return templates.TemplateResponse("help.html", {"request": request, "current_user": user})
''', encoding="utf-8")

# 12. app/web/routes/lipsync.py
(routes_dir / "lipsync.py").write_text('''from fastapi import APIRouter, Request, Depends
from app.web.templating import templates
from app.web.auth import get_current_user

router = APIRouter(prefix="/lipsync", tags=["lipsync"])


@router.get("")
def lipsync_view(request: Request, user = Depends(get_current_user)):
    return templates.TemplateResponse("help.html", {"request": request, "current_user": user})
''', encoding="utf-8")

# 13. app/web/routes/users.py
(routes_dir / "users.py").write_text('''from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.web.templating import templates
from app.web.auth import get_current_user, require_roles

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
def users_view(request: Request, user: User = Depends(require_roles(["admin"])), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return templates.TemplateResponse("change_password.html", {"request": request, "current_user": user, "users": users})
''', encoding="utf-8")

# 14. app/web/routes/topics.py
(routes_dir / "topics.py").write_text('''from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Topic
from app.web.templating import templates
from app.web.auth import get_current_user

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("")
def topics_view(request: Request, user = Depends(get_current_user), db: Session = Depends(get_db)):
    topics = db.query(Topic).all()
    return templates.TemplateResponse("help.html", {"request": request, "current_user": user, "topics": topics})
''', encoding="utf-8")

# 15. app/web/routes/audit.py
(routes_dir / "audit.py").write_text('''from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import WorkflowAuditLog
from app.web.templating import templates
from app.web.auth import get_current_user, require_roles

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def audit_view(request: Request, user = Depends(require_roles(["admin", "lead"])), db: Session = Depends(get_db)):
    logs = db.query(WorkflowAuditLog).order_by(WorkflowAuditLog.created_at.desc()).limit(100).all()
    return templates.TemplateResponse("audit.html", {"request": request, "current_user": user, "logs": logs})
''', encoding="utf-8")

# 16. app/web/routes/benchmark.py
(routes_dir / "benchmark.py").write_text('''from fastapi import APIRouter, Request, Depends
from app.web.templating import templates
from app.web.auth import get_current_user
from app.benchmark_report import build_report

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


@router.get("")
def benchmark_view(request: Request, user = Depends(get_current_user)):
    report = build_report()
    return templates.TemplateResponse("benchmark.html", {"request": request, "current_user": user, "report": report})
''', encoding="utf-8")

# 17. app/web/routes/setup_routes.py
(routes_dir / "setup_routes.py").write_text('''from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from app.web.templating import templates
from app.services.runtime_config import setup_completed, mark_setup_completed

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("")
def setup_page(request: Request):
    if setup_completed():
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse("setup.html", {"request": request})


@router.post("/finish")
def setup_finish():
    mark_setup_completed()
    return RedirectResponse(url="/dashboard", status_code=303)
''', encoding="utf-8")

# 18. app/web/routes/system_routes.py
(routes_dir / "system_routes.py").write_text('''from fastapi import APIRouter, Request, Depends
from app.web.templating import templates
from app.web.auth import get_current_user

router = APIRouter(tags=["system"])


@router.get("/system/settings")
def system_settings(request: Request, user = Depends(get_current_user)):
    return templates.TemplateResponse("system_settings.html", {"request": request, "current_user": user})


@router.get("/help")
def help_page(request: Request, user = Depends(get_current_user)):
    return templates.TemplateResponse("help.html", {"request": request, "current_user": user})


@router.get("/support")
def support(request: Request, user = Depends(get_current_user)):
    return templates.TemplateResponse("support.html", {"request": request, "current_user": user})
''', encoding="utf-8")

print("Generated all web routes")
