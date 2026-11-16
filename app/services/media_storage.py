import os
import shutil
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from PIL import Image

from app.config import settings

logger = logging.getLogger("ak_news.media_storage")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def prepare_media_target_path(post_id: int, filename: str) -> Path:
    folder = settings.raw_media_dir / str(post_id)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / filename


def is_disk_full_or_critical() -> bool:
    usage = shutil.disk_usage(settings.data_dir)
    pct = (usage.used / usage.total) * 100
    return pct >= settings.DISK_WATCHDOG_THRESHOLD_PERCENT


def get_disk_usage() -> Dict[str, Any]:
    usage = shutil.disk_usage(settings.data_dir)
    return {
        "total_gb": round(usage.total / (1024**3), 2),
        "used_gb": round(usage.used / (1024**3), 2),
        "free_gb": round(usage.free / (1024**3), 2),
        "used_percent": round((usage.used / usage.total) * 100, 1),
    }


def verify_image_integrity(path: Path) -> bool:
    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False


def is_local_media_path(path_str: str) -> bool:
    try:
        p = Path(path_str).resolve()
        raw_root = settings.raw_media_dir.resolve()
        edited_root = settings.edited_media_dir.resolve()
        return p.is_relative_to(raw_root) or p.is_relative_to(edited_root)
    except Exception:
        return False


def source_quota_allows(db, source_id: int, incoming_bytes: int = 0) -> bool:
    """Ensure source channel has not exceeded storage quota."""
    if is_disk_full_or_critical():
        logger.warning("Disk space critical! Rejecting incoming media.")
        return False
    return True


def add_source_usage(db, source_id: int, bytes_added: int) -> None:
    from app.models import SourceChannel
    if not source_id or bytes_added <= 0:
        return
    try:
        source = db.query(SourceChannel).filter_by(id=source_id).first()
        if source:
            mb = bytes_added / (1024 * 1024)
            source.used_mb = (source.used_mb or 0.0) + round(mb, 2)
            db.commit()
    except Exception:
        db.rollback()


def dedupe_media_item(db, post_id: int, file_path: Path) -> bool:
    """Check if same media SHA256 was already ingested in another post."""
    if not file_path.exists():
        return False
    try:
        from app.models import MediaItem
        h = file_sha256(file_path)
        existing = db.query(MediaItem).filter(MediaItem.sha256 == h).first()
        return existing is not None
    except Exception:
        return False


_watchdog_metadata_only: bool = False

def refresh_disk_watchdog(entered: bool) -> None:
    global _watchdog_metadata_only
    _watchdog_metadata_only = entered

def recompute_source_usage(db) -> None:
    from sqlalchemy import func
    from app.models import SourceChannel, RawPost, MediaItem
    try:
        sources = db.query(SourceChannel).all()
        for s in sources:
            total = db.query(func.coalesce(func.sum(MediaItem.file_size_bytes), 0)).join(RawPost, MediaItem.raw_post_id == RawPost.id).filter(RawPost.source_channel_id == s.id).scalar()
            s.storage_used_bytes = int(total or 0)
        db.commit()
    except Exception as e:
        logger.warning(f"Error recomputing source storage usage: {e}")
        db.rollback()
