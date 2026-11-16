import os
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, LipsyncJob, GeneratedVideo
from app.web.templating import templates
from app.web.auth import get_current_user, require_editor
from app.services import lipsync_service

router = APIRouter(prefix="", tags=["lipsync"])


class LipsyncRenderRequest(BaseModel):
    mode: str = lipsync_service.MODE_TALKING_PHOTO
    avatar_id: Optional[str] = "local"
    text: str = ""
    voice: str = "edge:vi-VN-HoaiMyNeural"
    speed: float = 1.0
    layout: str = lipsync_service.LAYOUT_PIP_BR
    source_media_url: Optional[str] = None
    post_id: Optional[int] = None


class CompositeRequest(BaseModel):
    talking_video_path: str
    background_media_path: Optional[str] = None
    layout: str = lipsync_service.LAYOUT_PIP_BR
    aspect_ratio: str = "9:16"
    post_id: Optional[int] = None


@router.get("/editor/video")
@router.get("/lipsync")
def lipsync_view(
    request: Request,
    post_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.models import RawPost, MediaItem
    from app.config import settings
    from app.services import video_languages

    post = None
    if post_id:
        post = db.query(RawPost).filter(RawPost.id == post_id).first()
    if not post:
        post = db.query(RawPost).order_by(RawPost.id.desc()).first()
    if not post:
        post = RawPost(id=0, original_text="Video mới", edited_text="Video mới")

    avatars = lipsync_service.list_preset_avatars()
    langs = list(video_languages.LANGUAGES.values())
    default_lang = "vi"
    voices_flat = []
    for lcode, ldata in video_languages.LANGUAGES.items():
        for v in ldata.get("voices", []):
            voices_flat.append({
                "lang": lcode,
                "key": v["id"],
                "label": v["name"]
            })

    latest_video = None
    source_media = None
    if post.id:
        latest_video = db.query(GeneratedVideo).filter(GeneratedVideo.raw_post_id == post.id).order_by(GeneratedVideo.id.desc()).first()
        source_media = db.query(MediaItem).filter(MediaItem.raw_post_id == post.id).first()

    return templates.TemplateResponse(
        "video_editor.html",
        {
            "request": request,
            "current_user": user,
            "post": post,
            "avatars": avatars,
            "languages": langs,
            "video_language": default_lang,
            "voices": voices_flat,
            "default_voice": "vi-VN-HoaiMyNeural",
            "voiceover_text": post.resolved_text or "",
            "studio": {},
            "latest_video": latest_video,
            "source_video_item": source_media,
            "app_version": getattr(settings, "APP_VERSION", "1.0.0")
        }
    )


@router.get("/api/lipsync/avatars")
def get_avatars(user: User = Depends(get_current_user)):
    presets = lipsync_service.list_preset_avatars()
    return {"ok": True, "avatars": presets}


@router.post("/api/lipsync/avatars/upload")
async def upload_avatar(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    user: User = Depends(require_editor)
):
    avatar_dir = Path("data/avatars")
    avatar_dir.mkdir(parents=True, exist_ok=True)
    filename = f"user_{user.id}_{file.filename}"
    out_path = avatar_dir / filename
    with open(out_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {
        "ok": True,
        "avatar": {
            "id": f"upload:{filename}",
            "name": name or file.filename,
            "image_path": str(out_path),
            "custom": True
        }
    }


@router.post("/api/lipsync/render")
async def render_lipsync_job(
    req: LipsyncRenderRequest,
    user: User = Depends(require_editor),
    db: Session = Depends(get_db)
):
    job = lipsync_service.dispatch_lipsync_job(
        mode=req.mode,
        avatar_path=req.avatar_id or "local",
        text=req.text,
        voice=req.voice,
        speed=req.speed,
        source_media_path=req.source_media_url,
        layout=req.layout,
        post_id=req.post_id
    )
    return {"ok": True, "job_id": job.id, "status": job.status}


@router.get("/api/lipsync/jobs/{job_id}")
def get_lipsync_job_status(job_id: int, user: User = Depends(get_current_user)):
    status = lipsync_service.get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ lipsync")
    return {"ok": True, "job": status}


@router.post("/api/lipsync/composite")
async def composite_talking_video(
    req: CompositeRequest,
    user: User = Depends(require_editor),
    db: Session = Depends(get_db)
):
    out_video = Path("data/outputs") / f"composite_{Path(req.talking_video_path).stem}.mp4"
    ok = lipsync_service.composite_video(
        talking_video_path=Path(req.talking_video_path),
        background_media_path=Path(req.background_media_path) if req.background_media_path else None,
        output_path=out_video,
        layout=req.layout,
        aspect_ratio=req.aspect_ratio
    )
    if not ok or not out_video.exists():
        raise HTTPException(status_code=500, detail="Không thể ghép nối video nhân vật ảo")

    if req.post_id:
        record = GeneratedVideo(
            raw_post_id=req.post_id,
            status="ready",
            video_type="composite_lipsync",
            file_path=str(out_video)
        )
        db.add(record)
        db.commit()

    return {"ok": True, "video_path": str(out_video)}
