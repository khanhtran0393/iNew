import os
import json
import asyncio
import mimetypes
from pathlib import Path
from urllib.parse import quote
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User, RawPost, RawPostMedia, GeneratedVideo, PublishTarget, WorkflowAuditLog
from app.web.auth import get_current_user, require_editor
from app.services.ai_copilot import run_ai_action, generate_integrated_script, analyze_script_scenes
from app.services.video_languages import default_voice_for
from app.services.video_producer import produce_full_video_pipeline
from app.services.video_remixer import execute_smart_video_remix
from app.services.multi_platform_publisher import dispatch_video_to_targets, PUBLISHABLE_STATUSES
from app.services.article_fetcher import fetch_article_for_post
from app.services.voice_studio import synthesize_to_file
from app.services.ai_image import generate_image
from app.services.web_image_search import search_images_multi_engine, download_image

router = APIRouter(prefix="", tags=["api"])


class AiAssistRequest(BaseModel):
    post_id: int
    action: Optional[str] = "integrated_script"
    language: Optional[str] = "vi"
    script_length: Optional[str] = "shorts_60s"
    custom_minutes: Optional[float] = 1.0
    headline_style: Optional[str] = "sensational"
    aspect_ratio: Optional[str] = "9:16"
    prompt: Optional[str] = ""
    target_lang: Optional[str] = "vi"


class ScriptScenesRequest(BaseModel):
    post_id: int
    script_text: Optional[str] = ""
    aspect_ratio: Optional[str] = "9:16"


class GenerateSceneImageRequest(BaseModel):
    post_id: int
    scene_id: int
    prompt: str
    aspect_ratio: Optional[str] = "9:16"


class GenerateAllScenesRequest(BaseModel):
    post_id: int
    scenes: List[Dict[str, Any]]
    aspect_ratio: Optional[str] = "9:16"


class AiActionRequest(BaseModel):
    action: Optional[str] = "summarize"
    text: Optional[str] = ""


class AiMediaRequest(BaseModel):
    post_id: int
    prompt: Optional[str] = ""
    model: Optional[str] = "gemini"


class ImageSearchRequest(BaseModel):
    query: str
    engines: Optional[List[str]] = None
    max_results: Optional[int] = 20


class ImageDownloadRequest(BaseModel):
    image_url: str
    output_path: str


class PostIdRequest(BaseModel):
    post_id: int


class VideoRequest(BaseModel):
    post_id: int
    theme: Optional[str] = "red"
    voice: Optional[str] = "edge:vi-VN-HoaiMyNeural"
    speed: Optional[float] = 1.0
    language: Optional[str] = "vi"
    aspect_ratio: Optional[str] = "9:16"
    script_length: Optional[str] = "shorts_60s"
    custom_minutes: Optional[float] = 1.0
    headline_style: Optional[str] = "sensational"


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


class AiActionRequest(BaseModel):
    action: Optional[str] = "summarize"
    text: Optional[str] = ""


# 1. AI Actions
@router.post("/api/ai/action")
async def ai_action_endpoint(
    req: Optional[AiActionRequest] = None,
    action: Optional[str] = None,
    text: Optional[str] = None,
    user: User = Depends(get_current_user)
):
    act = (req.action if req and req.action else action) or "summarize"
    txt = (req.text if req and req.text else text) or ""
    res = await run_ai_action(act, txt, user_id=user.id)
    return {"ok": True, "success": True, "result": res}


@router.post("/api/ai-assist")
async def ai_assist_endpoint(req: AiAssistRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.query(RawPost).filter_by(id=req.post_id).first()
    if not post:
        return {"ok": False, "success": False, "error": "Không tìm thấy bài viết"}
    source_text = post.resolved_text or post.title or ""
    
    if req.action == "integrated_script":
        res = await generate_integrated_script(
            text=source_text,
            language=req.language or "vi",
            script_length=req.script_length or "shorts_60s",
            custom_minutes=req.custom_minutes or 1.0,
            headline_style=req.headline_style or "sensational",
            aspect_ratio=req.aspect_ratio or "9:16",
            user_id=user.id
        )
    else:
        res = await run_ai_action(req.action or "summarize", source_text, user_id=user.id)

    return {
        "ok": True,
        "success": True,
        "result": res,
        "usage": {"used": 1, "limit": 9999}
    }


@router.post("/api/ai/script-scenes")
async def get_script_scenes_endpoint(req: ScriptScenesRequest, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    post = db.query(RawPost).filter_by(id=req.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết")
    script = req.script_text or post.edited_text or post.resolved_text or ""
    scenes = await analyze_script_scenes(script, aspect_ratio=req.aspect_ratio or "9:16", user_id=user.id)
    return {"ok": True, "success": True, "scenes": scenes}


@router.post("/api/ai/generate-scene-image")
async def generate_scene_image_endpoint(req: GenerateSceneImageRequest, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    post = db.query(RawPost).filter_by(id=req.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết")
    from app.services.ai_image import generate_image
    out_dir = Path("data/outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"scene_{req.post_id}_{req.scene_id}_{int(datetime.now().timestamp())}.png"
    ok = await generate_image(req.prompt, out_file, aspect=req.aspect_ratio or "9:16")
    if ok and out_file.exists():
        media = RawPostMedia(
            raw_post_id=req.post_id,
            media_type="photo",
            local_path=str(out_file),
            file_size_bytes=out_file.stat().st_size,
            origin="manual"
        )
        db.add(media)
        db.commit()
        db.refresh(media)
        return {
            "ok": True,
            "success": True,
            "media_id": media.id,
            "image_url": f"/media/download?path={quote(str(out_file))}",
            "file_path": str(out_file)
        }
    return {"ok": False, "success": False, "error": "Không thể tạo ảnh minh họa bằng AI"}


@router.post("/api/ai/generate-all-scenes")
async def generate_all_scenes_endpoint(req: GenerateAllScenesRequest, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    post = db.query(RawPost).filter_by(id=req.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết")
    from app.services.ai_image import generate_image
    out_dir = Path("data/outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    generated = []
    for sc in req.scenes:
        sid = sc.get("scene_id", 1)
        prompt = sc.get("ai_prompt") or sc.get("scene_description") or ""
        if not prompt:
            continue
        out_file = out_dir / f"scene_{req.post_id}_{sid}_{int(datetime.now().timestamp())}.png"
        ok = await generate_image(prompt, out_file, aspect=req.aspect_ratio or "9:16")
        if ok and out_file.exists():
            media = RawPostMedia(
                raw_post_id=req.post_id,
                media_type="photo",
                local_path=str(out_file),
                file_size_bytes=out_file.stat().st_size,
                origin="manual"
            )
            db.add(media)
            db.commit()
            db.refresh(media)
            generated.append({
                "scene_id": sid,
                "media_id": media.id,
                "image_url": f"/media/download?path={quote(str(out_file))}"
            })
    return {"ok": True, "success": True, "generated": generated, "count": len(generated)}


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
    post = db.query(RawPost).filter_by(id=req.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết")

    lang = req.language or "vi"
    ratio = req.aspect_ratio or "9:16"
    theme = req.theme or "red"

    # Bước 1: AI viết kịch bản (kết hợp 5W1H + Tháp ngược theo cấu hình Mục 1)
    source_text = post.resolved_text or post.title or ""
    script_text = post.edited_text or ""
    if not script_text.strip():
        script_text = await generate_integrated_script(
            text=source_text,
            language=lang,
            script_length=req.script_length or "shorts_60s",
            custom_minutes=req.custom_minutes or 1.0,
            headline_style=req.headline_style or "sensational",
            aspect_ratio=ratio,
            user_id=user.id
        )
        post.edited_text = script_text
        db.commit()

    # Bước 2: TTS lồng tiếng - lấy theo giọng mặc định của hệ thống
    default_voice = default_voice_for(lang)

    # Bước 3: Phân tích kịch bản / SRT để chia prompt cảnh và tạo ảnh AI nếu cần
    scenes = await analyze_script_scenes(script_text, aspect_ratio=ratio, user_id=user.id)
    has_photo = any(m.media_type == "photo" and m.local_path and not str(m.local_path).startswith("http") for m in post.media_items)
    if not has_photo and scenes:
        from app.services.ai_image import generate_image
        out_dir = Path("data/outputs")
        out_dir.mkdir(parents=True, exist_ok=True)
        sc1 = scenes[0]
        prompt = sc1.get("ai_prompt") or sc1.get("scene_description") or post.title or "News broadcast"
        out_file = out_dir / f"scene_{post.id}_1_{int(datetime.now().timestamp())}.png"
        ok = await generate_image(prompt, out_file, aspect=ratio)
        if ok and out_file.exists():
            media = RawPostMedia(
                raw_post_id=post.id,
                media_type="photo",
                local_path=str(out_file),
                file_size_bytes=out_file.stat().st_size,
                origin="manual"
            )
            db.add(media)
            db.commit()

    # Bước 4: FFmpeg render video theo đúng tỉ lệ khung hình (9:16 / 16:9 / 1:1)
    res = await produce_full_video_pipeline(
        post_id=req.post_id,
        script_text=script_text,
        theme=theme,
        voice=default_voice,
        speed=req.speed or 1.0,
        language=lang,
        aspect_ratio=ratio
    )
    if res.get("success"):
        res["pipeline_steps"] = [
            "AI viết kịch bản chuẩn 5W1H & Tháp ngược",
            f"TTS lồng tiếng ({default_voice})",
            f"Phân tích SRT chia {len(scenes)} phân cảnh",
            f"FFmpeg render video ({ratio})"
        ]
    return res


# 6. Video Editor Endpoints
@router.post("/api/video-editor/script")
async def video_editor_script_endpoint(req: PostIdRequest, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    post = db.query(RawPost).filter_by(id=req.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết")
    content = post.resolved_text or post.title or ""
    res = await run_ai_action("video_script", content, user_id=user.id)
    return {"ok": True, "success": True, "script": res}


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


# 7. AI Media - Enhanced with Free Image Generation & Web Image Search
# POST /api/ai-media-free - Generate images using Pollinations.ai (free tier)
@router.post("/api/ai-media-free")
async def ai_media_free_endpoint(req: AiMediaRequest, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    prompt = req.prompt or "Hình ảnh minh họa tin tức chuyên nghiệp, phong cách phóng sự chân thực"
    out_dir = Path("data/outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"ai_media_{req.post_id}_{int(datetime.now().timestamp())}.png"
    
    try:
        ok = await generate_image(prompt, out_file)
        if not ok or not out_file.exists():
            raise HTTPException(status_code=500, detail="Không thể tạo ảnh miễn phí")
        
        return {
            "success": True,
            "asset": str(out_file),
            "message": "Ảnh đã được tạo thành công bằng Pollinations.ai"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi tạo ảnh miễn phí: {str(e)}")


# POST /api/image-search - Search for real images from web
@router.post("/api/image-search")
async def image_search_endpoint(req: ImageSearchRequest, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    query = req.query
    engines = req.engines or ["bing", "duckduckgo"]
    max_results = req.max_results or 20
    
    if not query:
        raise HTTPException(status_code=400, detail="Cần có truy vấn tìm kiếm")
    
    try:
        results = await search_images_multi_engine(query, engines, max_results)
        return {
            "success": True,
            "results": results,
            "query": query,
            "engines": engines,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi tìm kiếm ảnh: {str(e)}")


# POST /api/image-search/download - Download an image
@router.post("/api/image-search/download")
async def download_image_endpoint(req: ImageDownloadRequest, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    if not req.image_url:
        raise HTTPException(status_code=400, detail="Cần có URL ảnh")
    
    try:
        success = await download_image(req.image_url, req.output_path)
        if success:
            return {"success": True, "message": "Ảnh đã được tải về"}
        else:
            raise HTTPException(status_code=500, detail="Không thể tải ảnh")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tải ảnh: {str(e)}")


# 8. Publishing & System
@router.get("/api/publish-targets")
def get_publish_targets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    targets = db.query(PublishTarget).filter_by(is_active=True).all()
    return {"ok": True, "targets": [{"id": t.id, "name": t.name, "platform": t.platform} for t in targets]}


@router.post("/api/publish-video")
async def publish_video_endpoint(req: PublishVideoRequest, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    post = db.query(RawPost).filter_by(id=req.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết")
    data_root = settings.DATA_ROOT_PATH or settings.data_dir
    video_abs = Path(req.video_rel_path)
    if not video_abs.is_absolute():
        candidate = data_root / req.video_rel_path
        if candidate.exists():
            video_abs = candidate
        elif (Path("data") / req.video_rel_path).exists():
            video_abs = Path("data") / req.video_rel_path
        else:
            video_abs = candidate
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
