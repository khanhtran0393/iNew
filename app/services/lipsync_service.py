import os
import sys
import uuid
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.config import settings
from app.services.proc import FFMPEG_BIN, FFPROBE_BIN, run, run_process_async

logger = logging.getLogger("ak_news.lipsync")

MODE_TALKING_PHOTO = "talking_photo"
MODE_VIDEO_LIPSYNC = "video_lipsync"

LAYOUT_FULL = "full"
LAYOUT_SPLIT = "split"
LAYOUT_PIP_BR = "pip_br"
LAYOUT_PIP_BL = "pip_bl"

# In-memory jobs tracker
_JOBS: Dict[str, Dict[str, Any]] = {}


def probe_duration(media_path: str) -> float:
    p = Path(media_path)
    if not p.exists():
        return 0.0
    try:
        cmd = [
            FFPROBE_BIN,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(p)
        ]
        proc = run(cmd)
        if proc.returncode == 0 and proc.stdout.strip():
            return float(proc.stdout.strip())
    except Exception as e:
        logger.warning(f"Could not probe duration for {media_path}: {e}")
    return 10.0


def list_preset_avatars() -> List[Dict[str, Any]]:
    avatars = [
        {"id": "mc_female_1", "name": "BTV Lan Anh (Áo dài đỏ)", "gender": "female", "path": "", "rel_path": "mc_female_1", "media_url": "/static/img/icon-256.png"},
        {"id": "mc_female_2", "name": "BTV Thu Hà (Công sở)", "gender": "female", "path": "", "rel_path": "mc_female_2", "media_url": "/static/img/icon-256.png"},
        {"id": "mc_male_1", "name": "BTV Minh Trí (Vest đen)", "gender": "male", "path": "", "rel_path": "mc_male_1", "media_url": "/static/img/icon-256.png"},
        {"id": "mc_male_2", "name": "BTV Quốc Anh (Sơ mi xanh)", "gender": "male", "path": "", "rel_path": "mc_male_2", "media_url": "/static/img/icon-256.png"},
    ]

    avatars_dir = settings.avatars_dir
    avatars_dir.mkdir(parents=True, exist_ok=True)

    # Scan for custom avatars uploaded by user
    for img_file in avatars_dir.glob("*.*"):
        if img_file.suffix.lower() in (".png", ".jpg", ".jpeg", ".mp4"):
            avatars.append({
                "id": img_file.stem,
                "name": f"Tự chọn: {img_file.name}",
                "gender": "custom",
                "path": str(img_file),
                "rel_path": img_file.name,
                "media_url": f"/avatars/{img_file.name}",
            })
    return avatars


async def render_talking_photo_clip(
    photo_path: str,
    audio_path: str,
    output_path: str,
    width: int = 1080,
    height: int = 1920
) -> bool:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG_BIN,
        "-y",
        "-loop", "1",
        "-i", str(photo_path),
        "-i", str(audio_path),
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(output_path)
    ]
    code, stdout, stderr = await run_process_async(cmd)
    if code != 0:
        logger.error(f"Error in render_talking_photo_clip: {stderr}")
        return False
    return True


async def render_video_lipsync_clip(
    video_path: str,
    audio_path: str,
    output_path: str,
    layout: str = LAYOUT_FULL,
    bg_video_path: Optional[str] = None
) -> bool:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if layout == LAYOUT_FULL:
        cmd = [
            FFMPEG_BIN,
            "-y",
            "-stream_loop", "-1",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_path)
        ]
    elif layout == LAYOUT_PIP_BR and bg_video_path:
        filter_complex = "[1:v]scale=360:640[mc];[0:v][mc]overlay=W-w-40:H-h-120:shortest=1[v]"
        cmd = [
            FFMPEG_BIN,
            "-y",
            "-stream_loop", "-1",
            "-i", str(bg_video_path),
            "-stream_loop", "-1",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "2:a:0",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_path)
        ]
    else:  # Standard audio replacement fallback
        cmd = [
            FFMPEG_BIN,
            "-y",
            "-stream_loop", "-1",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_path)
        ]

    code, stdout, stderr = await run_process_async(cmd)
    if code != 0:
        logger.error(f"Error in render_video_lipsync_clip: {stderr}")
        return False
    return True


async def start_lipsync_job(
    mode: str,
    source_media: str,
    voice_audio: str,
    layout: str = LAYOUT_FULL,
    bg_media: Optional[str] = None
) -> str:
    job_id = uuid.uuid4().hex[:12]
    out_dir = settings.lipsync_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"lipsync_{job_id}.mp4"

    _JOBS[job_id] = {
        "job_id": job_id,
        "mode": mode,
        "status": "processing",
        "output_path": str(out_file),
        "created_at": probe_duration(voice_audio),
        "error": None,
    }

    async def _worker():
        try:
            if mode == MODE_TALKING_PHOTO:
                ok = await render_talking_photo_clip(source_media, voice_audio, str(out_file))
            else:
                ok = await render_video_lipsync_clip(source_media, voice_audio, str(out_file), layout=layout, bg_video_path=bg_media)

            if ok and out_file.exists():
                _JOBS[job_id]["status"] = "completed"
            else:
                _JOBS[job_id]["status"] = "failed"
                _JOBS[job_id]["error"] = "FFmpeg render process failed."
        except Exception as e:
            _JOBS[job_id]["status"] = "failed"
            _JOBS[job_id]["error"] = str(e)

    asyncio.create_task(_worker())
    return job_id


def get_lipsync_job(job_id: str) -> Optional[Dict[str, Any]]:
    return _JOBS.get(job_id)


def get_job_status(job_id: int) -> Optional[Dict[str, Any]]:
    from app.database import SessionLocal
    from app.models import LipsyncJob
    db = SessionLocal()
    try:
        j = db.query(LipsyncJob).filter_by(id=job_id).first()
        if j:
            return {
                "id": j.id,
                "status": j.status,
                "output_path": j.output_path,
                "error": j.error_message
            }
        return _JOBS.get(str(job_id))
    finally:
        db.close()


def dispatch_lipsync_job(
    mode: str,
    avatar_path: str,
    text: str,
    voice: str = "edge:vi-VN-HoaiMyNeural",
    speed: float = 1.0,
    source_media_path: Optional[str] = None,
    layout: str = LAYOUT_PIP_BR,
    post_id: Optional[int] = None
) -> Any:
    from app.database import SessionLocal
    from app.models import LipsyncJob
    from app.services.voice_studio import synthesize_to_file

    db = SessionLocal()
    out_dir = settings.lipsync_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    planned_audio = str(out_dir / f"lipsync_voice_{post_id or uuid.uuid4().hex[:8]}.mp3")
    job = LipsyncJob(
        source_media_path=avatar_path or "local",
        audio_path=planned_audio,
        layout=layout,
        engine="ffmpeg_lipsync",
        status="processing"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id
    db.close()

    async def _async_worker():
        from app.database import SessionLocal
        from app.models import LipsyncJob
        out_dir = settings.lipsync_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        audio_file = out_dir / f"lipsync_voice_{job_id}.mp3"
        out_file = out_dir / f"lipsync_{job_id}.mp4"

        try:
            # 1. Synthesize voice
            await synthesize_to_file(text, voice, audio_file, speed=speed)

            # 2. Resolve avatar
            resolved_avatar = avatar_path
            if avatar_path.startswith("upload:"):
                resolved_avatar = str(settings.data_dir / "avatars" / avatar_path.replace("upload:", ""))
            elif not os.path.exists(resolved_avatar):
                # Use default icon as talking photo avatar
                from app.resources import get_asset_path
                def_ico = get_asset_path("app/web/static/img/icon-256.png")
                resolved_avatar = str(def_ico)

            # 3. Render talking photo or clip
            ok = await render_talking_photo_clip(resolved_avatar, str(audio_file), str(out_file))

            db = SessionLocal()
            try:
                j = db.query(LipsyncJob).filter_by(id=job_id).first()
                if j:
                    if ok and out_file.exists():
                        j.status = "completed"
                        j.output_path = str(out_file)
                    else:
                        j.status = "failed"
                        j.error_message = "Không thể ghép video nhân vật ảo"
                    db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Lipsync worker error: {e}")
            db = SessionLocal()
            try:
                j = db.query(LipsyncJob).filter_by(id=job_id).first()
                if j:
                    j.status = "failed"
                    j.error_message = str(e)
                    db.commit()
            finally:
                db.close()

    asyncio.create_task(_async_worker())
    return job


def composite_video(
    talking_video_path: Path,
    background_media_path: Optional[Path],
    output_path: Path,
    layout: str = LAYOUT_PIP_BR,
    aspect_ratio: str = "9:16"
) -> bool:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    w, h = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)

    if not background_media_path or not background_media_path.exists():
        # Just scale talking video
        cmd = [
            FFMPEG_BIN,
            "-y",
            "-i", str(talking_video_path),
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            str(output_path)
        ]
    else:
        # PiP Overlay
        filter_complex = f"[1:v]scale={w//3}:{h//3}[mc];[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2[bg];[bg][mc]overlay=W-w-30:H-h-100:shortest=1[v]"
        cmd = [
            FFMPEG_BIN,
            "-y",
            "-stream_loop", "-1",
            "-i", str(background_media_path),
            "-i", str(talking_video_path),
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-shortest",
            str(output_path)
        ]

    try:
        res = run(cmd)
        return res.returncode == 0 and output_path.exists()
    except Exception as e:
        logger.error(f"composite_video failed: {e}")
        return False
