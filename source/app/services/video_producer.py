"""Automated news video rendering and assembly."""

import os
from pathlib import Path
from app.config import settings
from app.services import proc


def get_media_duration_seconds(media_path: str) -> float:
    ffprobe = str(Path(r"D:\iNew-Setup-1.0.5\source\ffmpeg\ffprobe.exe"))
    if not os.path.exists(ffprobe):
        ffprobe = "ffprobe"
    cmd = [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(media_path)]
    res = proc.run(cmd)
    try:
        return float(res.stdout.strip())
    except Exception:
        return 0.0


def create_remix_overlay_graphic(hook_title: str, source_title: str, output_png: str, width: int = 1080, height: int = 1920, language: str = "vi"):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Simple card box
    draw.rectangle([(50, 100), (width - 50, 400)], fill=(0, 0, 0, 180))
    draw.text((80, 130), hook_title[:80], fill=(255, 255, 255, 255))
    draw.text((80, 250), f"Nguồn: {source_title[:60]}", fill=(200, 200, 200, 255))
    img.save(output_png)
