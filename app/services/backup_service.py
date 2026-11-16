import os
import gzip
import json
import shutil
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.config import settings

logger = logging.getLogger("ak_news.backup")

BACKUP_INTERVAL_HOURS = 6
BACKUP_KEEP_DAYS = 7
INFO_FILE_NAME = "latest_backup_info.json"


def _sqlite_path(url: Optional[str] = None) -> Path:
    db_url = url or settings.DATABASE_URL
    if db_url.startswith("sqlite:///"):
        raw_path = db_url.replace("sqlite:///", "")
        return Path(raw_path).resolve()
    return settings.data_dir / "ak_news.db"


def backup_sqlite_now(keep_days: int = BACKUP_KEEP_DAYS) -> Dict[str, Any]:
    backup_dir = settings.backup_dir
    backup_dir.mkdir(parents=True, exist_ok=True)

    db_path = _sqlite_path()
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found at {db_path}")

    now = datetime.now(timezone.utc)
    ts_str = now.strftime("%Y%m%d_%H%M%S")
    gz_filename = f"ak_news_backup_{ts_str}.db.gz"
    target_gz = backup_dir / gz_filename
    part_gz = backup_dir / f"{gz_filename}.part"

    # Safely take an online consistent SQLite snapshot via native backup API
    import sqlite3
    temp_raw = backup_dir / f"{gz_filename}.raw"
    src_conn = sqlite3.connect(str(db_path))
    dst_conn = sqlite3.connect(str(temp_raw))
    try:
        with src_conn, dst_conn:
            src_conn.backup(dst_conn)
    finally:
        src_conn.close()
        dst_conn.close()

    orig_size = temp_raw.stat().st_size
    with open(temp_raw, "rb") as f_in:
        with gzip.open(part_gz, "wb", compresslevel=6) as f_out:
            shutil.copyfileobj(f_in, f_out)
    temp_raw.unlink(missing_ok=True)

    if part_gz.exists():
        part_gz.replace(target_gz)

    compressed_size = target_gz.stat().st_size

    # Update latest backup info
    info = {
        "latest_backup_file": target_gz.name,
        "latest_backup_path": str(target_gz),
        "created_at": now.isoformat(),
        "original_size_bytes": orig_size,
        "compressed_size_bytes": compressed_size,
        "compression_ratio": round((compressed_size / orig_size) * 100, 2) if orig_size > 0 else 100.0,
    }

    info_path = backup_dir / INFO_FILE_NAME
    try:
        info_path.write_text(json.dumps(info, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not write {INFO_FILE_NAME}: {e}")

    # Prune older backups
    pruned_count = prune_old_backups(keep_days=keep_days)
    info["pruned_count"] = pruned_count
    logger.info(f"Database backed up to {target_gz.name} ({compressed_size} bytes, pruned {pruned_count} old files)")
    return info


def prune_old_backups(keep_days: int = BACKUP_KEEP_DAYS) -> int:
    backup_dir = settings.backup_dir
    if not backup_dir.exists():
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    pruned = 0

    for item in backup_dir.glob("ak_news_backup_*.db*"):
        try:
            mtime = datetime.fromtimestamp(item.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                item.unlink(missing_ok=True)
                pruned += 1
        except Exception as e:
            logger.warning(f"Failed to prune old backup {item}: {e}")

    return pruned


def list_backups() -> List[Dict[str, Any]]:
    backup_dir = settings.backup_dir
    if not backup_dir.exists():
        return []

    results = []
    for item in sorted(backup_dir.glob("ak_news_backup_*.db*"), reverse=True):
        if item.name.endswith(".part"):
            continue
        try:
            stat = item.stat()
            results.append({
                "filename": item.name,
                "path": str(item),
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })
        except Exception:
            continue
    return results


def get_backup_status() -> Dict[str, Any]:
    backup_dir = settings.backup_dir
    info_path = backup_dir / INFO_FILE_NAME
    latest = None
    if info_path.exists():
        try:
            latest = json.loads(info_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    backups = list_backups()
    total_size = sum(b["size_bytes"] for b in backups)
    return {
        "backup_enabled": True,
        "backup_dir": str(backup_dir),
        "total_backups": len(backups),
        "total_size_bytes": total_size,
        "latest": latest or (backups[0] if backups else None),
    }


async def backup_worker_loop(interval_hours: int = BACKUP_INTERVAL_HOURS):
    logger.info(f"Database backup worker started (every {interval_hours}h).")
    while True:
        try:
            backup_sqlite_now()
        except Exception as e:
            logger.error(f"Scheduled backup failed: {e}")
        await asyncio.sleep(interval_hours * 3600)
