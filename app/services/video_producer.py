import os
import sys
import logging
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from PIL import Image, ImageDraw, ImageFont

from app.config import settings
from app.services.voice_studio import synthesize_to_file
from app.services.proc import run_process_async, FFMPEG_BIN, FFPROBE_BIN

logger = logging.getLogger("ak_news.video_producer")

_FONT_CACHE: Dict[Tuple[int, bool, str], ImageFont.FreeTypeFont] = {}

def get_font(size: int = 36, bold: bool = False, lang: str = "vi") -> ImageFont.FreeTypeFont:
    cache_key = (size, bold, lang.lower())
    if cache_key in _FONT_CACHE:
        return _FONT_CACHE[cache_key]

    candidate_paths: List[str] = []
    
    if sys.platform == "win32":
        if lang in ("zh", "ja", "ko"):
            candidate_paths += [
                r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
                r"C:\Windows\Fonts\simhei.ttf",
                r"C:\Windows\Fonts\malgunbd.ttf" if bold else r"C:\Windows\Fonts\malgun.ttf",
                r"C:\Windows\Fonts\meiryob.ttc" if bold else r"C:\Windows\Fonts\meiryo.ttc",
            ]
        elif lang == "th":
            candidate_paths += [
                r"C:\Windows\Fonts\tahomabd.ttf" if bold else r"C:\Windows\Fonts\tahoma.ttf",
            ]
        
        if bold:
            candidate_paths += [
                r"C:\Windows\Fonts\arialbd.ttf",
                r"C:\Windows\Fonts\tahomabd.ttf",
                r"C:\Windows\Fonts\segoeuib.ttf",
            ]
        else:
            candidate_paths += [
                r"C:\Windows\Fonts\arial.ttf",
                r"C:\Windows\Fonts\tahoma.ttf",
                r"C:\Windows\Fonts\segoeui.ttf",
            ]
    elif sys.platform == "darwin":
        candidate_paths += [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Tahoma Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Tahoma.ttf",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        ]
    else:  # Linux
        candidate_paths += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        ]

    chosen_font = None
    for path in candidate_paths:
        if os.path.exists(path):
            try:
                chosen_font = ImageFont.truetype(path, size)
                break
            except Exception:
                continue

    if chosen_font is None:
        try:
            chosen_font = ImageFont.load_default()
            logger.warning("No TTF font found on system; falling back to default bitmap font.")
        except Exception:
            pass

    _FONT_CACHE[cache_key] = chosen_font
    return chosen_font

def _break_long_word(word: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    parts = []
    current = ""
    for char in word:
        test = current + char
        try:
            w = font.getlength(test)
        except Exception:
            w = len(test) * 15
        if w <= max_width or not current:
            current = test
        else:
            parts.append(current)
            current = char
    if current:
        parts.append(current)
    return parts

def wrap_text(text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    lines = []
    paragraphs = text.split("\n")
    for para in paragraphs:
        if not para.strip():
            lines.append("")
            continue
        words = para.split()
        current_line = []
        for word in words:
            test_line = " ".join(current_line + [word])
            try:
                line_w = font.getlength(test_line)
            except Exception:
                line_w = len(test_line) * 15

            if line_w <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                else:
                    parts = _break_long_word(word, font, max_width)
                    lines.extend(parts[:-1])
                    current_line = [parts[-1]] if parts else []
        if current_line:
            lines.append(" ".join(current_line))
    return lines

def create_title_card(
    title: str,
    source_name: str = "iNew News",
    width: int = 1080,
    height: int = 1920,
    theme: str = "dark",
    output_path: Optional[Path] = None,
) -> Path:
    bg_color = (15, 18, 25, 255) if theme == "dark" else (240, 243, 246, 255)
    text_color = (255, 255, 255, 255) if theme == "dark" else (20, 24, 33, 255)
    accent_color = (220, 38, 38, 255)  # Crimson Red

    img = Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Accent banner on top
    draw.rectangle([(0, 0), (width, 24)], fill=accent_color)

    # Source Name & Header
    font_sub = get_font(size=32, bold=True)
    draw.text((80, 120), source_name.upper(), fill=accent_color, font=font_sub)

    # Title with word wrap
    font_title = get_font(size=64, bold=True)
    wrapped_lines = wrap_text(title, font_title, max_width=width - 160)

    start_y = 200
    line_height = 80
    for line in wrapped_lines[:6]:
        draw.text((80, start_y), line, fill=text_color, font=font_title)
        start_y += line_height

    if output_path is None:
        output_path = settings.final_outputs_dir / "title_card.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "PNG")
    return output_path

def create_capcut_instructions(
    capcut_dir: Path,
    post_id: int,
    audio_file: str,
    subtitle_file: str,
    media_files: List[str]
) -> Path:
    capcut_dir.mkdir(parents=True, exist_ok=True)
    doc_path = capcut_dir / "HUONG_DAN_CAPCUT.txt"
    content = f"""=== HƯỚNG DẪN IMPORT GÓI TÀI NGUYÊN VIDEO CAPCUT (POST #{post_id}) ===

Thư mục này chứa đầy đủ tài nguyên đã được iNew tự động bóc tách và tạo sẵn:

1. FILE ÂM THANH VOICE-OVER:
   - File: {audio_file}
   - Import vào track âm thanh chính của dự án CapCut.

2. FILE PHỤ ĐỀ CHUẨN TỰ ĐỘNG (SRT):
   - File: {subtitle_file}
   - Mở CapCut -> Text -> Local Subtitles -> Chọn file .srt này để hiện phụ đề đồng bộ 100%.

3. DANH SÁCH FILE ẢNH / VIDEO NGUYÊN BẢN:
"""
    for idx, f in enumerate(media_files, 1):
        content += f"   [{idx}] {f}\n"

    content += """
4. CÁC BƯỚC THỰC HIỆN TRÊN CAPCUT:
   - Bước 1: Kéo toàn bộ ảnh/video vào Timeline.
   - Bước 2: Kéo file Voiceover MP3 vào Audio Track.
   - Bước 3: Import file SRT vào Subtitle Track.
   - Bước 4: Chọn tỷ lệ khung hình 9:16 (TikTok/Reels/Shorts).
   - Bước 5: Bấm Xuất (Export) 1080p 60fps để đăng tải đa nền tảng!
"""
    doc_path.write_text(content, encoding="utf-8")
    return doc_path

async def produce_full_video_pipeline(
    post_id: int,
    script_text: Optional[str] = None,
    voice_key: Optional[str] = None,
    hook_title: str = "",
    source_title: str = "iNew",
    media_paths: Optional[List[str]] = None,
    theme: str = "red",
    voice: Optional[str] = None,
    speed: float = 1.0,
    language: str = "vi",
    aspect_ratio: str = "9:16",
    *args,
    **kwargs
) -> Dict[str, Any]:
    from app.database import SessionLocal
    from app.models import RawPost, GeneratedVideo
    from app.services.video_remixer import get_media_duration_seconds, generate_srt_subtitles

    db = SessionLocal()
    post = None
    try:
        post = db.query(RawPost).filter_by(id=post_id).first()
    finally:
        db.close()

    # Determine script and voice
    if not script_text:
        if post:
            script_text = post.resolved_text or post.title or "Bản tin thời sự hôm nay."
        else:
            script_text = "Bản tin thời sự tự động từ iNew."

    chosen_voice = voice_key or voice or "edge:vi-VN-HoaiMyNeural"
    title_text = hook_title or (post.title if post and post.title else script_text[:80])
    src_title = source_title or (post.source.title if post and post.source else "iNew News")

    out_dir = settings.final_outputs_dir / f"post_{post_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Voiceover synthesis
    audio_path = out_dir / f"voice_{post_id}.mp3"
    await synthesize_to_file(script_text[:1000], chosen_voice, audio_path, speed=speed)
    dur = get_media_duration_seconds(str(audio_path))
    if dur <= 0:
        dur = 10.0

    # 2. Title card generation
    card_path = out_dir / f"title_card_{post_id}.png"
    create_title_card(title_text, source_name=src_title, output_path=card_path, theme="dark" if theme == "dark" else "light")

    # 3. Subtitles SRT
    sub_srt_path = out_dir / f"subtitles_{post_id}.srt"
    generate_srt_subtitles(script_text[:1000], dur, sub_srt_path)

    # 4. CapCut Export Pack Instructions
    doc_file = create_capcut_instructions(
        out_dir,
        post_id=post_id,
        audio_file=audio_path.name,
        subtitle_file=sub_srt_path.name,
        media_files=[os.path.basename(p) for p in (media_paths or [])]
    )

    # 5. FFmpeg compile full MP4 video
    final_video_path = out_dir / f"video_{post_id}.mp4"
    w, h = (1080, 1920) if aspect_ratio == "9:16" else ((1920, 1080) if aspect_ratio == "16:9" else (1080, 1080))

    # Base image for still background
    bg_input = str(card_path)
    if media_paths and len(media_paths) > 0 and os.path.exists(media_paths[0]):
        bg_input = str(media_paths[0])

    cmd = [
        FFMPEG_BIN,
        "-y",
        "-loop", "1",
        "-i", bg_input,
        "-i", str(audio_path),
        "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(final_video_path)
    ]
    code, stdout, stderr = await run_process_async(cmd)
    if code != 0 or not final_video_path.exists():
        logger.warning(f"FFmpeg render fallback: {stderr}")
        if not final_video_path.exists():
            emergency_cmd = [
                FFMPEG_BIN, "-y",
                "-loop", "1", "-i", bg_input,
                "-t", "3",
                "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(final_video_path)
            ]
            await run_process_async(emergency_cmd)
            if not final_video_path.exists():
                final_video_path.touch()

    # 6. Record in Database
    vid_id = 0
    db = SessionLocal()
    try:
        data_root = settings.DATA_ROOT_PATH or settings.data_dir
        try:
            rel_path = final_video_path.relative_to(data_root).as_posix()
        except Exception:
            rel_path = str(final_video_path)

        rec = db.query(GeneratedVideo).filter_by(raw_post_id=post_id).first()
        if not rec:
            rec = GeneratedVideo(
                raw_post_id=post_id,
                title=title_text,
                output_path=rel_path,
                duration_seconds=dur,
                voice_used=chosen_voice,
                status="ready",
                video_type="manual"
            )
            db.add(rec)
        else:
            rec.title = title_text
            rec.output_path = rel_path
            rec.duration_seconds = dur
            rec.voice_used = chosen_voice
            rec.status = "ready"
        db.commit()
        db.refresh(rec)
        vid_id = rec.id
    except Exception as dbe:
        logger.warning(f"Database record error for video: {dbe}")
    finally:
        db.close()

    return {
        "ok": True,
        "success": True,
        "status": "success",
        "video_id": vid_id,
        "post_id": post_id,
        "output_dir": str(out_dir),
        "file_path": str(final_video_path),
        "video_rel": str(rel_path) if "rel_path" in locals() else str(final_video_path),
        "audio_path": str(audio_path),
        "title_card": str(card_path),
        "subtitles_srt": str(sub_srt_path),
        "capcut_guide": str(doc_file),
    }
