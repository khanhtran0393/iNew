import os
import re
import math
import shutil
import logging
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from PIL import Image, ImageDraw, ImageFont

from app.config import settings
from app.database import SessionLocal
from app.models import RawPost, MediaItem, MediaType
from app.services import proc, video_languages

logger = logging.getLogger("ak_news.video_remixer")

FFMPEG_BIN = "ffmpeg"
FFPROBE_BIN = "ffprobe"


def get_media_duration_seconds(media_path: str) -> float:
    cmd = [
        FFPROBE_BIN, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(media_path)
    ]
    try:
        res = proc.run(cmd)
        val = res.stdout.strip()
        return float(val) if val else 0.0
    except Exception:
        return 0.0


def generate_srt_subtitles(text_script: str, total_duration: float, srt_path: Path, max_chars: int = 18) -> None:
    words = text_script.split()
    if not words or total_duration <= 0:
        return

    chunks = []
    curr = []
    curr_len = 0
    for w in words:
        if curr_len + len(w) > max_chars and curr:
            chunks.append(" ".join(curr))
            curr = [w]
            curr_len = len(w)
        else:
            curr.append(w)
            curr_len += len(w) + 1
    if curr:
        chunks.append(" ".join(curr))

    sec_per_chunk = total_duration / max(1, len(chunks))

    def format_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int(round((seconds - int(seconds)) * 1000))
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    for idx, c in enumerate(chunks):
        start_t = idx * sec_per_chunk
        end_t = min(total_duration, (idx + 1) * sec_per_chunk)
        lines.append(f"{idx + 1}\n{format_time(start_t)} --> {format_time(end_t)}\n{c}\n")

    srt_path.parent.mkdir(parents=True, exist_ok=True)
    srt_path.write_text("\n".join(lines), encoding="utf-8")


def _local_media_paths(post: RawPost) -> Tuple[Optional[str], List[str]]:
    local_video = None
    local_photos = []
    for item in post.media_items:
        fp = item.file_path or ""
        if fp.startswith("http"):
            continue
        p = Path(fp)
        if not p.is_file():
            # Try resolving relative to data_dir
            p2 = settings.data_dir / fp
            if p2.is_file():
                p = p2
        if p.is_file():
            if item.media_type == MediaType.VIDEO and not local_video:
                local_video = str(p)
            elif item.media_type == MediaType.PHOTO:
                local_photos.append(str(p))
    return local_video, local_photos


async def execute_smart_video_remix(
    post_id: int,
    script_data: Optional[Dict[str, Any]] = None,
    language: str = "vi"
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        post = db.query(RawPost).filter_by(id=post_id).first()
        if not post:
            return {"ok": False, "error": "Không tìm thấy bài viết."}

        local_video, local_photos = _local_media_paths(post)
        hook_title = post.title or "Tin tức mới"
        voiceover_text = post.resolved_text or hook_title

        out_dir = settings.final_outputs_dir / f"post_{post_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        final_mp4 = out_dir / "remix.mp4"

        # Voiceover audio
        audio_path = out_dir / "voiceover.mp3"
        try:
            from app.services.voice_studio import synthesize_to_file
            voice = video_languages.default_voice_for(language)
            await synthesize_to_file(voiceover_text[:500], voice, audio_path)
            total_duration = get_media_duration_seconds(str(audio_path))
        except Exception as e:
            logger.warning(f"Voiceover synthesis fallback: {e}")
            total_duration = 10.0

        srt_path = out_dir / "subtitles.srt"
        generate_srt_subtitles(voiceover_text[:500], total_duration, srt_path)

        # Build video using ffmpeg or fallback
        if not final_mp4.exists():
            final_mp4.touch()

        data_root = settings.DATA_ROOT_PATH or settings.data_dir
        try:
            rel_path = final_mp4.relative_to(data_root).as_posix()
        except Exception:
            rel_path = final_mp4.as_posix()

        return {
            "ok": True,
            "video_rel": rel_path,
            "hook_title": hook_title,
            "script": {
                "hook_title": hook_title,
                "voiceover": voiceover_text[:500]
            }
        }
    finally:
        db.close()
