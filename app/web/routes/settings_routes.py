from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Request, Depends, Form, HTTPException, Body
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User, AiApiKey, SourceChannel, PublishTarget, AppSetting, AiTaskRoute
from app.web.templating import templates
from app.web.auth import get_current_user, user_is_admin, require_admin
from app.services.llm_providers import PROVIDERS, complete
from app.services.auto_video_service import get_auto_video_config, set_auto_video_config
from app.services.desktop import currently_lan, set_allow_lan, lan_addresses, request_restart
from app.services.updates import check_for_updates, get_cached_update_info
from app.telegram_login import send_code_request, verify_login_code

router = APIRouter(prefix="", tags=["settings"])


# 1. AI Settings
@router.get("/settings/ai-config")
@router.get("/settings/ai")
def ai_config_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    keys = db.query(AiApiKey).all()
    active_keys = [k for k in keys if k.is_active]

    providers = {
        "gemini": {
            "name": "Google Gemini",
            "models": ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"],
            "url": "https://aistudio.google.com/",
        },
        "openai": {
            "name": "OpenAI (ChatGPT)",
            "models": ["gpt-4o-mini", "gpt-4o"],
            "url": "https://platform.openai.com/api-keys",
        },
        "anthropic": {
            "name": "Anthropic Claude",
            "models": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
            "url": "https://console.anthropic.com/",
        },
        "deepseek": {
            "name": "DeepSeek",
            "models": ["deepseek-chat", "deepseek-reasoner"],
            "url": "https://platform.deepseek.com/",
        },
    }

    purposes = [
        {"code": "rewrite", "label": "Biên tập lại tin tức", "desc": "Viết lại tiêu đề và nội dung ngắn gọn"},
        {"code": "verify", "label": "Kiểm chứng & đối chiếu", "desc": "Đối chiếu sự thật và cảnh báo tin giả"},
        {"code": "auto_video", "label": "Dựng kịch bản video ngắn", "desc": "Tạo kịch bản TikTok/Reels/Shorts 9:16"},
        {"code": "smart_crop", "label": "Phân tích ảnh / Smart Crop", "desc": "Xác định trọng tâm ảnh và tiêu điểm"},
    ]

    routes_rows = db.query(AiTaskRoute).all()
    routes = {r.purpose: {"provider": r.provider, "model": r.model} for r in routes_rows}
    if not routes:
        routes = {
            "rewrite": {"provider": "gemini", "model": "gemini-1.5-flash"},
            "verify": {"provider": "gemini", "model": "gemini-1.5-pro"},
            "auto_video": {"provider": "gemini", "model": "gemini-1.5-flash"},
            "smart_crop": {"provider": "gemini", "model": "gemini-1.5-flash"},
        }

    auto_video_cfg = get_auto_video_config(db)
    publish_targets = db.query(PublishTarget).all()

    return templates.TemplateResponse("settings_ai.html", {
        "request": request,
        "current_user": user,
        "ai_keys": keys,
        "total_keys": len(keys),
        "active_keys": len(active_keys),
        "total_calls": 0,
        "providers": providers,
        "routes": routes,
        "purposes": purposes,
        "ai_usage": [],
        "auto_video_config": auto_video_cfg,
        "publish_targets": publish_targets,
    })


@router.post("/settings/ai-config/create")
def ai_key_create(
    provider: str = Form(...),
    label: str = Form(...),
    api_key: str = Form(...),
    base_url: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    from app.services.security_crypto import encrypt_secret
    k = AiApiKey(
        provider=provider.strip(),
        label=label.strip(),
        api_key_encrypted=encrypt_secret(api_key.strip()),
        base_url=(base_url or "").strip() or None,
        model=(model or "").strip() or None,
        is_active=True
    )
    db.add(k)
    db.commit()
    return RedirectResponse(url="/settings/ai", status_code=303)


@router.post("/settings/ai-config/{key_id}/delete")
def ai_key_delete(key_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    k = db.query(AiApiKey).filter_by(id=key_id).first()
    if k:
        db.delete(k)
        db.commit()
    return RedirectResponse(url="/settings/ai", status_code=303)


@router.post("/settings/ai-config/{key_id}/toggle")
def ai_key_toggle(key_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    k = db.query(AiApiKey).filter_by(id=key_id).first()
    if k:
        k.is_active = not k.is_active
        db.commit()
    return RedirectResponse(url="/settings/ai", status_code=303)


@router.post("/settings/ai-routes/save")
def ai_routes_save(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    # Simple redirect back
    return RedirectResponse(url="/settings/ai", status_code=303)


@router.post("/settings/auto-video/save")
@router.post("/auto-video/save")
def auto_video_save(
    enabled: bool = Form(False),
    only_with_media: bool = Form(False),
    max_per_hour: int = Form(4),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    set_auto_video_config(db, enabled, only_with_media, max_per_hour)
    return RedirectResponse(url="/settings/ai", status_code=303)


@router.post("/settings/publish-targets/create")
def publish_target_create(
    name: str = Form(...),
    platform: str = Form(...),
    target_id: Optional[str] = Form(""),
    access_token: Optional[str] = Form(""),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    from app.services.security_crypto import encrypt_secret
    pt = PublishTarget(
        name=name.strip(),
        platform=platform.strip(),
        target_id=(target_id or "").strip(),
        access_token=encrypt_secret(access_token.strip()) if access_token else None,
        is_active=True
    )
    db.add(pt)
    db.commit()
    return RedirectResponse(url="/settings/ai", status_code=303)


@router.post("/settings/publish-targets/{target_id}/delete")
def publish_target_delete(target_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    pt = db.query(PublishTarget).filter_by(id=target_id).first()
    if pt:
        db.delete(pt)
        db.commit()
    return RedirectResponse(url="/settings/ai", status_code=303)


@router.post("/settings/publish-targets/{target_id}/toggle")
def publish_target_toggle(target_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    pt = db.query(PublishTarget).filter_by(id=target_id).first()
    if pt:
        pt.is_active = not pt.is_active
        db.commit()
    return RedirectResponse(url="/settings/ai", status_code=303)


@router.get("/settings/api/ai-models")
def get_ai_models():
    return {
        "gemini": ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"],
        "openai": ["gpt-4o-mini", "gpt-4o"],
        "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
        "deepseek": ["deepseek-chat", "deepseek-reasoner"],
    }


@router.post("/settings/api/ai-keys/test-direct")
@router.post("/api/ai-keys/test-direct")
async def ai_key_test_direct(
    provider: str = Body(..., embed=True),
    api_key: str = Body(..., embed=True),
    user: User = Depends(require_admin)
):
    try:
        res = await complete("Xin chào, hãy trả lời ngắn gọn: OK", provider=provider, api_key=api_key)
        return {"ok": True, "response": res}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/ai-keys/{key_id}/test")
async def ai_key_test_by_id(
    key_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    from app.services.security_crypto import decrypt_secret
    k = db.query(AiApiKey).filter_by(id=key_id).first()
    if not k:
        raise HTTPException(status_code=404, detail="Không tìm thấy khóa API")
    try:
        raw_key = decrypt_secret(k.api_key_encrypted)
        res = await complete("Xin chào, hãy trả lời ngắn gọn: OK", provider=k.provider, api_key=raw_key)
        return {"ok": True, "response": res}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# 2. Telegram Settings & Live Login
@router.get("/settings/telegram")
def telegram_settings_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    total_sources = db.query(SourceChannel).filter(SourceChannel.source_type == "telegram").count()
    linked_sources = db.query(SourceChannel).filter(
        SourceChannel.source_type == "telegram",
        SourceChannel.is_active == True
    ).count()

    from app.services.telegram_ingestion import ingestion_service
    is_conn = ingestion_service.is_connected()
    st = "running" if is_conn else "not_authorized"

    status = {
        "state": st,
        "connected": is_conn,
        "authorized": is_conn,
        "last_event_at": None,
        "last_catchup_at": None,
        "last_sync_summary": None,
    }

    return templates.TemplateResponse("telegram_settings.html", {
        "request": request,
        "current_user": user,
        "status": status,
        "api_id": settings.TELEGRAM_API_ID or "",
        "api_configured": bool(settings.TELEGRAM_API_ID and settings.TELEGRAM_API_HASH),
        "default_phone": "",
        "total_sources": total_sources,
        "linked_sources": linked_sources,
        "public_base_url": "https://t.me",
        "web_run": {"channels": total_sources, "failed": 0, "new_posts": 0},
        "web_run_at": datetime.now(timezone.utc),
        "code_sent": False,
        "need_password": False,
        "error_sources": [],
    })


@router.post("/settings/telegram/send-code")
async def settings_telegram_send_code(phone: str = Form(...)):
    api_id = int(settings.TELEGRAM_API_ID or 0)
    api_hash = settings.TELEGRAM_API_HASH or ""
    if not api_id or not api_hash:
        return RedirectResponse(url="/settings/telegram?err=Ch%C6%B0a+c%E1%BA%A5u+h%C3%ACnh+API+ID+v%C3%A0+Hash", status_code=303)
    res = await send_code_request(phone, api_id, api_hash)
    if not res.get("ok"):
        return RedirectResponse(url=f"/settings/telegram?err={res.get('error', 'L%E1%BB%97i+g%E1%BB%ADi+m%C3%A3')}", status_code=303)
    return RedirectResponse(url="/settings/telegram?ok=%C4%90%C3%A3+g%E1%BB%ADi+m%C3%A3+Telegram", status_code=303)


@router.post("/settings/telegram/verify")
async def settings_telegram_verify(code: str = Form(""), password: Optional[str] = Form(None)):
    res = await verify_login_code(code, password)
    if not res.get("ok"):
        return RedirectResponse(url=f"/settings/telegram?err={res.get('error', '%C4%90%C4%83ng+nh%E1%BA%ADp+th%E1%BA%A5t+b%E1%BA%A1i')}", status_code=303)
    return RedirectResponse(url="/settings/telegram?ok=%C4%90%C4%83ng+nh%E1%BA%ADp+Telegram+th%C3%A0nh+c%C3%B4ng", status_code=303)


@router.post("/settings/telegram/sync")
async def settings_telegram_sync():
    from app.services.telegram_web_collector import sync_public_channels
    await sync_public_channels()
    return RedirectResponse(url="/settings/telegram?ok=%C4%90%C3%A3+%C4%91%E1%BB%93ng+b%E1%BB%99+k%C3%AAnh+Telegram", status_code=303)


# 3. System Settings & LAN Bridge
@router.get("/settings/system")
@router.get("/system/settings")
def system_settings_view(
    request: Request,
    msg: Optional[str] = None,
    user: User = Depends(get_current_user)
):
    allow_lan = currently_lan()
    running_lan = currently_lan()
    lan_urls = [f"http://{ip}:{getattr(settings, 'PORT', 8000)}" for ip in lan_addresses()]
    upd = get_cached_update_info()

    return templates.TemplateResponse("system_settings.html", {
        "request": request,
        "current_user": user,
        "msg": msg,
        "allow_lan": allow_lan,
        "running_lan": running_lan,
        "lan_urls": lan_urls,
        "can_restart": True,
        "upd": upd,
    })


@router.post("/settings/system/lan")
def settings_system_lan(allow_lan: str = Form("off"), user: User = Depends(require_admin)):
    enable = (allow_lan.lower() in ("on", "true", "1"))
    set_allow_lan(enable)
    return RedirectResponse(url="/settings/system?msg=lan", status_code=303)


@router.post("/settings/system/check-update")
async def settings_system_check_update(user: User = Depends(require_admin)):
    await check_for_updates()
    return RedirectResponse(url="/settings/system?msg=checked", status_code=303)


@router.post("/settings/system/restart")
def settings_system_restart(user: User = Depends(require_admin)):
    request_restart()
    return RedirectResponse(url="/settings/system?msg=restarted", status_code=303)
