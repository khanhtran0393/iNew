import asyncio
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import AppSetting, GeneratedVideo, RawPost, RawPostStatus, WorkflowStatus
from app.services.video_remixer import execute_smart_video_remix

logger = logging.getLogger("ak_news.auto_video")
_render_semaphore = asyncio.Semaphore(1)

DEFAULTS = {
    "auto_video_enabled": "false",
    "auto_video_only_with_media": "true",
    "auto_video_max_per_hour": "4"
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get(db: Session, key: str) -> str:
    row = db.query(AppSetting).filter_by(key=key).first()
    if row and row.value is not None:
        return row.value
    return DEFAULTS.get(key, "")


def _set(db: Session, key: str, value: str) -> None:
    row = db.query(AppSetting).filter_by(key=key).first()
    if not row:
        row = AppSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.commit()


def get_auto_video_config(db: Session) -> Dict[str, Any]:
    return {
        "enabled": _get(db, "auto_video_enabled").lower() == "true",
        "only_with_media": _get(db, "auto_video_only_with_media").lower() == "true",
        "max_per_hour": max(0, min(60, int(_get(db, "auto_video_max_per_hour") or 4)))
    }


def set_auto_video_config(db: Session, enabled: bool, only_with_media: bool, max_per_hour: int) -> None:
    _set(db, "auto_video_enabled", "true" if enabled else "false")
    _set(db, "auto_video_only_with_media", "true" if only_with_media else "false")
    _set(db, "auto_video_max_per_hour", str(max(0, min(60, max_per_hour))))


def pick_auto_video_candidates(db: Session, only_with_media: bool = True, limit: int = 5) -> List[int]:
    already = [r[0] for r in db.query(GeneratedVideo.raw_post_id).all()]
    since = _utcnow() - timedelta(hours=24)
    q = db.query(RawPost.id).filter(
        RawPost.created_at >= since,
        RawPost.status != RawPostStatus.DUPLICATE,
        RawPost.workflow_status != WorkflowStatus.REJECTED,
        RawPost.is_source_deleted.is_(False)
    )
    if already:
        q = q.filter(RawPost.id.notin_(already))
    if only_with_media:
        q = q.filter(RawPost.has_media.is_(True))

    q = q.order_by(RawPost.id.desc()).limit(limit)
    return [r[0] for r in q.all()]


async def create_video_for_post(post_id: int, mode: str = "manual", language: str = "vi") -> Dict[str, Any]:
    db = SessionLocal()
    try:
        post = db.query(RawPost).filter_by(id=post_id).first()
        if not post:
            return {"success": False, "error": "Không tìm thấy bài viết"}

        record = GeneratedVideo(
            raw_post_id=post_id,
            status="processing",
            mode=mode
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        record_id = record.id
    finally:
        db.close()

    async with _render_semaphore:
        try:
            res = await execute_smart_video_remix(post_id=post_id)
            db = SessionLocal()
            try:
                rec = db.query(GeneratedVideo).filter_by(id=record_id).first()
                if rec:
                    if res.get("ok"):
                        rec.status = "ready"
                        rec.file_path = res.get("video_rel") or ""
                        rec.hook_title = res.get("hook_title") or ""
                        if res.get("script"):
                            rec.script_json = json.dumps(res["script"], ensure_ascii=False)
                    else:
                        rec.status = "failed"
                        rec.error_message = res.get("error") or "Lỗi tạo video"
                    db.commit()
            finally:
                db.close()
            return res
        except Exception as e:
            logger.exception(f"Video render crashed for post #{post_id}: {e}")
            db = SessionLocal()
            try:
                rec = db.query(GeneratedVideo).filter_by(id=record_id).first()
                if rec:
                    rec.status = "failed"
                    rec.error_message = f"Lỗi tạo video: {e}"
                    db.commit()
            finally:
                db.close()
            return {"success": False, "error": str(e)}


async def run_auto_video_cycle(db: Session) -> None:
    cfg = get_auto_video_config(db)
    if not cfg["enabled"]:
        return

    one_hour_ago = _utcnow() - timedelta(hours=1)
    made_last_hour = db.query(GeneratedVideo).filter(
        GeneratedVideo.mode == "auto",
        GeneratedVideo.created_at >= one_hour_ago
    ).count()

    budget = max(0, cfg["max_per_hour"] - made_last_hour)
    if budget <= 0:
        return

    candidates = pick_auto_video_candidates(db, only_with_media=cfg["only_with_media"], limit=budget)
    for pid in candidates:
        logger.info(f"Auto video for post #{pid}: Start")
        res = await create_video_for_post(pid, mode="auto")
        logger.info(f"Auto video for post #{pid}: {'OK' if res.get('ok') else res.get('error')}")


async def auto_video_worker_loop():
    logger.info("Auto video worker started (draft videos only, never auto-publishes).")
    while True:
        try:
            db = SessionLocal()
            try:
                await run_auto_video_cycle(db)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Auto video worker error: {e}")
        await asyncio.sleep(60)
