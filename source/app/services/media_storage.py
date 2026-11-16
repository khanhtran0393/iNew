"""Local disk storage management and cleanup for media files."""

import os
from pathlib import Path
from app.config import settings


def get_media_full_path(relative_path: str) -> Path:
    return settings.data_dir / relative_path


def cleanup_stale_media(retention_days: int = 14) -> int:
    import time
    now = time.time()
    cutoff = now - (retention_days * 86400)
    removed = 0
    for folder in [settings.raw_media_dir, settings.edited_media_dir]:
        if not folder.exists():
            continue
        for f in folder.glob("*"):
            if f.is_file():
                try:
                    if f.stat().st_mtime < cutoff:
                        f.unlink()
                        removed += 1
                except Exception:
                    pass
    return removed
