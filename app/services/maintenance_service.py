import os
import shutil
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import ActionLog, GeneratedVideo, MediaItem, RawPost, User, Role, WorkflowStatus
from app.services.media_storage import (
    get_disk_usage,
    is_local_media_path,
    recompute_source_usage,
    refresh_disk_watchdog
)

logger = logging.getLogger("ak_news.maintenance")

DISK_WATCHDOG_THRESHOLD_PERCENT = 90.0
_last_disk_alert: Optional[datetime] = None
_last_emergency_cleanup: Optional[datetime] = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def send_disk_alert(disk: Dict[str, Any], db: Session) -> None:
    global _last_disk_alert
    now = _utcnow()
    if _last_disk_alert and (now - _last_disk_alert) < timedelta(hours=2):
        return

    used_pct = disk.get("used_percent", 0)
    free_gb = disk.get("free_bytes", 0) / (1024 ** 3)
    path = disk.get("path", "")

    msg = (
        f"⚠️ <b>CẢNH BÁO DUNG LƯỢNG Ổ ĐĨA iNew</b>\n\n"
        f"Ổ đĩa lưu trữ ({path}) đã sử dụng: <b>{used_pct:.1f}%</b> (vượt ngưỡng {DISK_WATCHDOG_THRESHOLD_PERCENT}%).\n"
        f"Dung lượng trống còn lại: <b>{free_gb:.2f} GB</b>.\n"
        f"Hệ thống đã tự động chuyển sang chế độ bảo vệ dữ liệu (metadata-only) và tạm dừng tải trước tệp media nặng."
    )

    try:
        from app.services.telegram_bot import send_telegram_message
        admins = db.query(User).join(User.role).filter(User.is_active.is_(True), Role.slug == "admin").all()
        for a in admins:
            tg_id = a.telegram_id or (int(a.telegram_user_id) if a.telegram_user_id and a.telegram_user_id.isdigit() else None)
            if tg_id:
                asyncio.create_task(send_telegram_message(tg_id, msg))
        _last_disk_alert = now
    except Exception as e:
        logger.warning(f"Disk alert to Telegram failed: {e}")


def _log_watchdog_transition(entered: bool, disk: Dict[str, Any], db: Session) -> None:
    action = "disk_metadata_only_on" if entered else "disk_metadata_only_off"
    used_pct = disk.get("used_percent", 0)
    msg = (
        f"Dung lượng ổ đĩa {used_pct:.1f}%: Chuyển sang chế độ lưu trữ tiêu đề + link, tạm dừng tải media nặng."
        if entered else
        f"Dung lượng ổ đĩa {used_pct:.1f}%: Đã giải phóng an toàn, khôi phục nạp media bình thường."
    )
    log_entry = ActionLog(
        action=action,
        entity_type="disk",
        entity_id=0,
        message=msg
    )
    db.add(log_entry)
    db.commit()


def check_disk_and_alert(db: Session) -> Dict[str, Any]:
    disk = get_disk_usage()
    used_pct = disk.get("used_percent", 0)
    entered = used_pct >= DISK_WATCHDOG_THRESHOLD_PERCENT
    refresh_disk_watchdog(entered)

    if entered:
        send_disk_alert(disk, db)
        _log_watchdog_transition(True, disk, db)
        if used_pct >= 95.0:
            logger.warning(f"Disk critical ({used_pct:.1f}%): Triggering emergency cleanup!")
            run_maintenance_once(media_days=7, video_days=3, emergency=True)
    return disk


def run_maintenance_once(media_days: int = 30, video_days: int = 14, emergency: bool = False) -> Dict[str, Any]:
    logger.info(f"Running maintenance sweep (media_days={media_days}, video_days={video_days}, emergency={emergency})...")
    db: Session = SessionLocal()
    freed_bytes = 0
    media_removed = 0
    videos_removed = 0

    try:
        now = _utcnow()
        media_cutoff = now - timedelta(days=media_days)
        video_cutoff = now - timedelta(days=video_days)

        # 1. Archive old posts
        old_posts = db.query(RawPost).filter(
            RawPost.created_at < media_cutoff,
            RawPost.workflow_status.notin_([WorkflowStatus.CLAIMED.value, WorkflowStatus.EDITING.value, WorkflowStatus.REVIEWING.value])
        ).all()
        for p in old_posts:
            p.workflow_status = WorkflowStatus.ARCHIVED.value
            p.status = "archived"

        # 2. Cleanup old media items
        old_media = db.query(MediaItem).filter(MediaItem.created_at < media_cutoff).all()
        for m in old_media:
            if m.file_path and os.path.exists(m.file_path):
                try:
                    freed_bytes += os.path.getsize(m.file_path)
                    os.remove(m.file_path)
                    media_removed += 1
                except OSError:
                    pass

        # 3. Cleanup old generated videos
        old_videos = db.query(GeneratedVideo).filter(GeneratedVideo.created_at < video_cutoff).all()
        for v in old_videos:
            if v.file_path and os.path.exists(v.file_path):
                try:
                    freed_bytes += os.path.getsize(v.file_path)
                    os.remove(v.file_path)
                    videos_removed += 1
                except OSError:
                    pass

        # 4. Clean temporary download files
        raw_media_dir = getattr(settings, "raw_media_dir", settings.data_dir / "media")
        if os.path.exists(raw_media_dir):
            for root, _, files in os.walk(raw_media_dir):
                for f in files:
                    if f.endswith(".part") or f.startswith("temp_"):
                        fpath = os.path.join(root, f)
                        try:
                            freed_bytes += os.path.getsize(fpath)
                            os.remove(fpath)
                        except OSError:
                            pass

        db.commit()
        recompute_source_usage(db)

        res = {
            "freed_mb": round(freed_bytes / (1024 * 1024), 2),
            "media_removed": media_removed,
            "videos_removed": videos_removed,
            "timestamp": now.isoformat()
        }
        logger.info(f"Maintenance finished: {res}")
        return res
    except Exception as e:
        logger.error(f"Maintenance sweep failed: {e}")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


async def maintenance_worker_loop(check_interval_seconds: int = 3600) -> None:
    logger.info("Maintenance background worker started.")
    while True:
        try:
            db = SessionLocal()
            try:
                await asyncio.to_thread(check_disk_and_alert, db)
                await asyncio.to_thread(run_maintenance_once)
            finally:
                db.close()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Maintenance loop error: {e}")
        await asyncio.sleep(check_interval_seconds)
