import os
import re
import shutil
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from PIL import Image, ImageDraw, ImageFont

from app.config import settings
from app.services import proc, video_languages
from app.services.video_remixer import get_media_duration_seconds, generate_srt_subtitles

logger = logging.getLogger("ak_news.video_editor")

FRAME_SIZES = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350)
}

THEME_COLORS = {
    "red": {
        "header_bg": (220, 38, 38, 255),
        "header_text": (255, 255, 255, 255),
        "source_text": (254, 202, 202, 255),
        "card_bg": (255, 255, 255, 245),
        "card_border": (239, 68, 68, 255),
        "tag_text": (185, 28, 28, 255),
        "footer_bg": (17, 24, 39, 230),
        "footer_text": (255, 255, 255, 255)
    },
    "blue": {
        "header_bg": (37, 99, 235, 255),
        "header_text": (255, 255, 255, 255),
        "source_text": (191, 219, 254, 255),
        "card_bg": (255, 255, 255, 245),
        "card_border": (59, 130, 246, 255),
        "tag_text": (29, 78, 216, 255),
        "footer_bg": (17, 24, 39, 230),
        "footer_text": (255, 255, 255, 255)
    },
    "gold": {
        "header_bg": (217, 119, 6, 255),
        "header_text": (255, 255, 255, 255),
        "source_text": (253, 230, 138, 255),
        "card_bg": (255, 255, 255, 245),
        "card_border": (245, 158, 11, 255),
        "tag_text": (180, 83, 9, 255),
        "footer_bg": (17, 24, 39, 230),
        "footer_text": (255, 255, 255, 255)
    },
    "dark": {
        "header_bg": (31, 41, 55, 255),
        "header_text": (255, 255, 255, 255),
        "source_text": (156, 163, 175, 255),
        "card_bg": (17, 24, 39, 245),
        "card_border": (75, 85, 99, 255),
        "tag_text": (229, 231, 235, 255),
        "footer_bg": (0, 0, 0, 230),
        "footer_text": (255, 255, 255, 255)
    }
}


@dataclass
class OverlayLayer:
    png: str
    start: float
    end: float
    width: int
    height: int


def _get_font(size: int) -> ImageFont.ImageFont:
    try:
        font_path = settings.app_dir / "web" / "static" / "fonts" / "InterVariable.woff2"
        return ImageFont.truetype(str(font_path), size)
    except Exception:
        return ImageFont.load_default()


def create_editor_overlay_graphic(
    width: int,
    height: int,
    header_text: str = "BẢN TIN NÓNG 24H",
    headline_text: str = "",
    source_text: str = "",
    footer_text: str = "iNew • THEO DÕI ĐỂ KHÔNG BỎ LỠ TIN MỚI",
    theme: str = "red",
    output_png: Optional[Path] = None,
    language: str = "vi"
) -> Path:
    colors = THEME_COLORS.get(theme, THEME_COLORS["red"])
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Header bar
    header_h = int(height * 0.08)
    draw.rectangle([(0, 0), (width, header_h)], fill=colors["header_bg"])
    h_font = _get_font(int(header_h * 0.45))
    draw.text((width // 2, header_h // 2), header_text.upper(), font=h_font, fill=colors["header_text"], anchor="mm")

    # Footer bar
    footer_h = int(height * 0.06)
    draw.rectangle([(0, height - footer_h), (width, height)], fill=colors["footer_bg"])
    f_font = _get_font(int(footer_h * 0.4))
    draw.text((width // 2, height - footer_h // 2), footer_text, font=f_font, fill=colors["footer_text"], anchor="mm")

    out = output_png or (settings.data_dir / "temp_overlay.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, format="PNG")
    return out


def render_custom_edited_video(spec: dict) -> Path:
    out_dir = settings.final_outputs_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    post_id = spec.get("post_id", 0)
    out_path = out_dir / f"custom_{post_id}.mp4"

    aspect = spec.get("aspect_ratio", "9:16")
    w, h = FRAME_SIZES.get(aspect, (1080, 1920))
    overlay_png = create_editor_overlay_graphic(
        width=w,
        height=h,
        header_text=spec.get("header_text", "BẢN TIN NÓNG 24H"),
        headline_text=spec.get("headline_text", ""),
        source_text=spec.get("source_text", "iNew"),
        footer_text=spec.get("footer_text", "iNew • THEO DÕI ĐỂ KHÔNG BỎ LỠ TIN MỚI"),
        theme=spec.get("theme", "red")
    )

    source_media = spec.get("source_media") or []
    audio_path = spec.get("voiceover_audio")

    return render_layered_video(
        source_media=source_media,
        voiceover_audio=audio_path,
        output_mp4=out_path,
        aspect_ratio=aspect,
        layers=[{"png": str(overlay_png), "start": 0.0, "end": 999.0, "width": w, "height": h}]
    )


def render_layered_video(
    source_media: List[str],
    voiceover_audio: Optional[str],
    output_mp4: Path,
    aspect_ratio: str = "9:16",
    framing: str = "blur",
    layers: Optional[List[Dict[str, Any]]] = None,
    start_time: float = 0.0,
    end_time: Optional[float] = None,
    voice_volume: float = 1.0,
    original_volume: float = 0.3,
    subtitle_text: Optional[str] = None,
    out_dir: Optional[Path] = None
) -> Path:
    output_mp4 = Path(output_mp4)
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    w, h = FRAME_SIZES.get(aspect_ratio, (1080, 1920))

    # Base media or fallback graphic
    base_input = None
    if source_media:
        for m in source_media:
            if m and os.path.exists(m):
                base_input = str(m)
                break

    if not base_input:
        base_input = str(create_editor_overlay_graphic(w, h))

    # If voiceover audio exists
    if voiceover_audio and os.path.exists(voiceover_audio):
        cmd = [
            proc.FFMPEG_BIN,
            "-y",
            "-loop", "1",
            "-i", base_input,
            "-i", str(voiceover_audio),
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_mp4)
        ]
    else:
        cmd = [
            proc.FFMPEG_BIN,
            "-y",
            "-loop", "1",
            "-i", base_input,
            "-t", "5",
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            str(output_mp4)
        ]

    try:
        proc.run(cmd)
    except Exception as e:
        logger.warning(f"render_layered_video error: {e}")
        if not output_mp4.exists():
            emergency_cmd = [
                proc.FFMPEG_BIN, "-y",
                "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:d=3",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(output_mp4)
            ]
            try:
                proc.run(emergency_cmd)
            except Exception:
                output_mp4.touch()

    return output_mp4
