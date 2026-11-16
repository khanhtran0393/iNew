"""AI Lip-sync video generation service."""

from pathlib import Path
from app.config import settings


async def create_lipsync_video(media_path: Path, audio_path: Path, layout: str = "pip_bottom_right") -> Path:
    out_file = settings.lipsync_dir / "lipsync_out.mp4"
    out_file.touch()
    return out_file
