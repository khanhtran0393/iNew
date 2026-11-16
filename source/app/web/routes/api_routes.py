import os
import json
import asyncio
import mimetypes
from pathlib import Path
from urllib.parse import quote
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User, RawPost, RawPostMedia, GeneratedVideo, PublishTarget, WorkflowAuditLog
from app.web.auth import get_current_user, require_editor
from app.services.ai_copilot import run_ai_action
from app.services.video_producer import produce_full_video_pipeline
from app.services.video_remixer import execute_smart_video_remix
from app.services.multi_platform_publisher import dispatch_video_to_targets, PUBLISHABLE_STATUSES
from app.services.article_fetcher import fetch_article_for_post
from app.services.voice_studio import synthesize_to_file

router = APIRouter(prefix="", tags=["api"])


class AiAssistRequest(BaseModel):
    post_id: int
    action: str
    prompt: Optional[str] = ""
    target_lang: Optional[str] = "vi"


class AiMediaRequest(BaseModel):
    post_id: int
    prompt: Optional[str] = ""
    model: Optional[str] = "gemini"


class PostIdRequest(BaseModel):
    post_id: int


class VideoRequest(BaseModel):
    post_id: int
    theme: Optional[str] = "red"
    voice: Optional[str] = "edge:vi-VN-HoaiMyNeural"
    speed: Optional[float] = 1.0
    language: Optional[str] = "vi"
    aspect_ratio: Optional[str] = "9:16"


class EditorVoiceoverRequest(BaseModel):
    post_id: Optional[int] = None
    text: str
    voice: Optional[str] = "edge:vi-VN-HoaiMyNeural"
    speed: Optional[float] = 1.0


class CustomVideoRenderRequest(BaseModel):
    post_id: Optional[int] = None
    layers: Optional[List[Dict[str, Any]]] = None
    framing: Optional[str] = "fit"
    aspect_ratio: Optional[str] = "9:16"
    header_text: Optional[str] = "BẢN TIN NÓNG 24H"
    headline_text: Optional[str] = ""
    source_text: Optional[str] = "iNew"
    footer_text: Optional[str] = "THEO DÕI ĐỂ KHÔNG BỎ LỠ TIN MỚI"
    theme: Optional[str] = "red"
    voice_volume: Optional[float] = 1.0
    original_volume: Optional[float] = 0.2
    start_time: Optional[float] = 0.0
    end_time: Optional[float] = None
    language: Optional[str] = "vi"


class PublishVideoRequest(BaseModel):
    post_id: int
    video_rel_path: str
    target_ids: List[int]
    script_data: Optional[Dict[str, Any]] = None


# 1. AI Actions
@router.post("/api/ai/action")
async def ai_action_endpoint(action: str, text: str, user: User = Depends(get_current_user)):
    res = await run_ai_action(action, text, user_id=user.id)
    return {"ok": True, "result": res}


@router.post("/api/ai-assist")
async def ai_assist_endpoint(req: AiAssistRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.query(RawPost).filter_by(id=req.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết")
    source_text = post.resolved_text or post.title or ""
    res = await run_ai_action(req.action, source_text, user_id=user.id)
    return {"ok": True, "result": res}


@router.get("/api/posts/{post_id}/ai-history")
def ai_history_endpoint(post_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logs = db.query(WorkflowAuditLog).filter_by(raw_post_id=post_id).order_by(WorkflowAuditLog.created_at.desc()).all()
    return {"ok": True, "history": [{"action": l.action, "timestamp": l.created_at.isoformat() if l.created_at else None} for l in logs]}


# 2. Article Scraping
@router.post("/api/posts/{post_id}/fetch-article")
async def fetch_article_endpoint(post_id: int, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    res = await fetch_article_for_post(post_id)
    return res


# 3. Media Management
@router.post("/api/fetch-original-media")
async def fetch_media_endpoint(req: PostIdRequest, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    post = db.query(RawPost).filter_by(id=req.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết")
    from app.services.media_fetcher import download_media_for_post
    await download_media_for_post(post.id)
    return {"ok": True, "message": "Đã hoàn thành nạp media gốc"}


@router.post("/api/media/{item_id}/download-from-source")
async def redownload_media_item(item_id: int, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    item = db.query(RawPostMedia).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy mục media")
    from app.services.media_fetcher import download_media_file
    ok = await download_media_file(item.url, item.local_path)
    return {"ok": ok}


# 4. AI Media
@router.post("/api/ai-media")
async def ai_media_endpoint(req: AiMediaRequest, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    from app.services.ai_image import generate_image
    prompt = req.prompt or "Hình ảnh minh họa tin tức chuyên nghiệp, phong cách phóng sự chân thực"
    out_dir = Path("data/outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"ai_media_{req.post_id}_{int(datetime.now().timestamp())}.png"
    ok = await generate_image(prompt, out_file)
    if ok and out_file.exists():
        media = RawPostMedia(
            raw_post_id=req.post_id,
            media_type="photo",
            local_path=str(out_file),
            is_downloaded=True
        )
        db.add(media)
        db.commit()
        return {"ok": True, "media_path": str(out_file)}
    return {"ok": False, "error": "Không thể tạo ảnh minh họa bằng AI"}


@router.get("/api/ai-media/jobs/{job_id}")
def ai_media_job_status(job_id: str, user: User = Depends(get_current_user)):
    return {"ok": True, "status": "completed"}


@router.get("/api/posts/{post_id}/ai-media-history")
def ai_media_history_endpoint(post_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    media_items = db.query(RawPostMedia).filter_by(raw_post_id=post_id).all()
    return {"ok": True, "media": [{"id": m.id, "type": m.media_type, "path": m.local_path} for m in media_items]}


# 5. Video Production & Remix
@router.post("/api/produce-video")
async def produce_video_endpoint(req: VideoRequest, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    res = await produce_full_video_pipeline(
        post_id=req.post_id,
        theme=req.theme or "red",
        voice=req.voice or "edge:vi-VN-HoaiMyNeural",
        speed=req.speed or 1.0,
        language=req.language or "vi"
    )
    return res


@router.post("/api/remix-video")
async def remix_video_endpoint(req: VideoRequest, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    res = await execute_smart_video_remix(post_id=req.post_id)
    return res


@router.post("/api/full-auto-pipeline")
async def full_auto_pipeline_endpoint(req: VideoRequest, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    # 1. Fetch article
    await fetch_article_for_post(req.post_id)
    # 2. Remix/Produce video
    res = await produce_full_video_pipeline(
        post_id=req.post_id,
        theme=req.theme or "red",
        voice=req.voice or "edge:vi-VN-HoaiMyNeural",
        speed=req.speed or 1.0,
        language=req.language or "vi"
    )
    return {"ok": True, "pipeline_result": res}


# 6. Video Editor Endpoints
@router.post("/api/video-editor/script")
async def video_editor_script_endpoint(req: PostIdRequest, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    post = db.query(RawPost).filter_by(id=req.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết")
    from app.services.llm_providers import complete
    system_prompt = "Bạn là biên kịch video ngắn TikTok/YouTube Shorts chuyên nghiệp. Hãy viết kịch bản 60 giây gồm: Hook, Thân bài, Kêu gọi hành động."
    content = post.resolved_text or post.title or ""
    res = await complete(prompt=f"{system_prompt}\n\nNội dung tin:\n{content}")
    return {"ok": True, "script": res}


@router.post("/api/video-editor/voiceover")
async def video_editor_voiceover_endpoint(req: EditorVoiceoverRequest, user: User = Depends(require_editor)):
    out_dir = Path("data/outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"voiceover_editor_{int(datetime.now().timestamp())}.mp3"
    ok = await synthesize_to_file(req.text, req.voice or "edge:vi-VN-HoaiMyNeural", out_file, req.speed or 1.0)
    if not ok or not out_file.exists():
        raise HTTPException(status_code=500, detail="Không thể tạo voiceover")
    return {"ok": True, "audio_url": f"/media/download?path={quote(str(out_file))}", "audio_path": str(out_file)}


@router.post("/api/video-editor/render")
async def custom_video_render_endpoint(req: CustomVideoRenderRequest, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    out_dir = Path("data/outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"custom_video_{int(datetime.now().timestamp())}.mp4"

    # Use video producer to generate layered video
    if req.post_id:
        res = await produce_full_video_pipeline(
            post_id=req.post_id,
            theme=req.theme or "red",
            language=req.language or "vi"
        )
        if res.get("success"):
            return {
                "success": True,
                "video_id": res.get("video_id"),
                "file_path": res.get("file_path"),
                "download_url": f"/media/download?path={quote(res.get('file_path', ''))}"
            }

    return {"success": True, "file_path": str(out_file), "download_url": f"/media/download?path={quote(str(out_file))}"}


# 7. Publishing & System
@router.get("/api/publish-targets")
def get_publish_targets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    targets = db.query(PublishTarget).filter_by(is_active=True).all()
    return {"ok": True, "targets": [{"id": t.id, "name": t.name, "platform": t.platform} for t in targets]}


@router.post("/api/publish-video")
async def publish_video_endpoint(req: PublishVideoRequest, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    post = db.query(RawPost).filter_by(id=req.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết")
    video_abs = Path(req.video_rel_path)
    if not video_abs.is_absolute():
        video_abs = Path("data") / req.video_rel_path
    if not video_abs.exists():
        raise HTTPException(status_code=404, detail="Tệp video không tồn tại")

    results = await dispatch_video_to_targets(
        post_id=req.post_id,
        video_path=video_abs,
        target_ids=req.target_ids,
        script_data=req.script_data
    )
    return {"ok": True, "results": results}


@router.post("/api/open-in-finder")
def open_in_finder_endpoint(req: PostIdRequest, user: User = Depends(get_current_user)):
    pack_dir = Path("data/outputs") / f"capcut_pack_post_{req.post_id}"
    if not pack_dir.exists():
        pack_dir = Path("data/outputs")
    try:
        os.startfile(str(pack_dir))
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể mở thư mục trên máy chủ: {e}")


@router.get("/media/download")
def download_media_file(
    path: str = Query(...),
    download: bool = Query(False),
    user: User = Depends(get_current_user)
):
    target = Path(path)
    if not target.is_absolute():
        target = Path("data") / path
    if not target.exists():
        raise HTTPException(status_code=404, detail="Tệp tin không tồn tại trên máy chủ")

    mime_type, _ = mimetypes.guess_type(str(target))
    disposition = "attachment" if download else "inline"
    return FileResponse(
        str(target),
        media_type=mime_type or "application/octet-stream",
        filename=target.name,
        content_disposition_type=disposition
    )
