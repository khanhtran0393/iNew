PUBLISHABLE_STATUSES = ["approved", "completed", "ready", "claimed"]

import os
import html
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.orm import Session
import httpx

from app.config import settings
from app.database import SessionLocal
from app.models import PublishLog, PublishTarget, RawPost
from app.services.security_crypto import decrypt_secret

logger = logging.getLogger("ak_news.multi_platform_publisher")


def _clip(text: str, limit: int = 1000) -> str:
    t = text.strip()
    if len(t) <= limit:
        return t
    return t[:limit].rstrip() + "…"


def build_telegram_caption(post: RawPost, target: PublishTarget, script_data: Optional[Dict[str, Any]] = None) -> str:
    hook = (script_data or {}).get("hook_title") or post.title or "BẢN TIN 24H"
    voiceover = (script_data or {}).get("voiceover") or post.cleaned_text or post.raw_text or ""
    source_title = getattr(post.source, "title", "") or "Báo Chính Thống"
    source_url = post.original_url or ""

    lines = [
        f"🔴 <b>{html.escape(hook)}</b>\n",
        f"{html.escape(_clip(voiceover, 600))}\n"
    ]
    if source_url:
        lines.append(f"🌐 <i>Nguồn tin: <a href=\"{source_url}\">{html.escape(source_title)}</a></i>")
    else:
        lines.append(f"🌐 <i>Nguồn tin: {html.escape(source_title)}</i>")

    hashtags = (script_data or {}).get("hashtags") or "#TinNong #ThoiSu #iNew"
    lines.append(f"\n{hashtags}")
    return "\n".join(lines)


async def publish_video_to_telegram(post: RawPost, target: PublishTarget, video_abs_path: str, script_data: Optional[Dict[str, Any]] = None, db: Optional[Session] = None) -> Tuple[bool, str]:
    token = decrypt_secret(target.access_token) if target.access_token else settings.TELEGRAM_BOT_TOKEN
    if not token:
        msg = "Chưa cấu hình TELEGRAM_BOT_TOKEN cho kênh này."
        if db:
            db.add(PublishLog(raw_post_id=post.id, publish_target_id=target.id, status="failed", error_message=msg))
            db.commit()
        return False, msg

    chat_id = target.target_id
    if not chat_id:
        msg = "Chưa cấu hình target_id (Chat ID / @channel)."
        if db:
            db.add(PublishLog(raw_post_id=post.id, publish_target_id=target.id, status="failed", error_message=msg))
            db.commit()
        return False, msg

    caption = build_telegram_caption(post, target, script_data)
    try:
        from aiogram import Bot
        from aiogram.types import FSInputFile
        bot = Bot(token=token)
        try:
            video_file = FSInputFile(video_abs_path)
            sent = await bot.send_video(
                chat_id=chat_id,
                video=video_file,
                caption=caption,
                parse_mode="HTML",
                supports_streaming=True
            )
            msg_id = str(sent.message_id)
            pub_url = f"https://t.me/{str(chat_id).replace('@', '')}/{msg_id}"
            if db:
                db.add(PublishLog(
                    raw_post_id=post.id,
                    publish_target_id=target.id,
                    status="success",
                    platform_post_id=msg_id,
                    published_url=pub_url
                ))
                db.commit()
            return True, pub_url
        finally:
            await bot.session.close()
    except Exception as e:
        logger.error(f"Error publishing to Telegram: {e}")
        err_msg = f"Lỗi gửi Telegram: {e}"
        if db:
            db.add(PublishLog(raw_post_id=post.id, publish_target_id=target.id, status="failed", error_message=err_msg))
            db.commit()
        return False, err_msg


async def publish_video_to_facebook(post: RawPost, target: PublishTarget, video_abs_path: str, script_data: Optional[Dict[str, Any]] = None, db: Optional[Session] = None) -> Tuple[bool, str]:
    token = decrypt_secret(target.access_token) if target.access_token else ""
    page_id = target.target_id
    if not token or not page_id:
        msg = "Thiếu Page ID hoặc Page Access Token cho Facebook."
        if db:
            db.add(PublishLog(raw_post_id=post.id, publish_target_id=target.id, status="failed", error_message=msg))
            db.commit()
        return False, msg

    hook = (script_data or {}).get("hook_title") or post.title or "BẢN TIN 24H"
    description = f"{hook}\n\nNguồn: {getattr(post.source, 'title', 'Báo chính thống')}\n#iNew"
    url = f"https://graph-video.facebook.com/v19.0/{page_id}/videos"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(video_abs_path, "rb") as vf:
                files = {"source": (Path(video_abs_path).name, vf, "video/mp4")}
                data = {"description": description, "access_token": token}
                res = await client.post(url, data=data, files=files)

            if res.status_code in (200, 201):
                fb_res = res.json()
                video_id = fb_res.get("id", "")
                post_url = f"https://facebook.com/{video_id}"
                if db:
                    db.add(PublishLog(
                        raw_post_id=post.id,
                        publish_target_id=target.id,
                        status="success",
                        platform_post_id=video_id,
                        published_url=post_url
                    ))
                    db.commit()
                return True, post_url
            else:
                err = f"Lỗi Facebook API: {res.text}"
                if db:
                    db.add(PublishLog(raw_post_id=post.id, publish_target_id=target.id, status="failed", error_message=err))
                    db.commit()
                return False, err
    except Exception as e:
        logger.error(f"Error publishing to Facebook: {e}")
        err = f"Lỗi kết nối Facebook: {e}"
        if db:
            db.add(PublishLog(raw_post_id=post.id, publish_target_id=target.id, status="failed", error_message=err))
            db.commit()
        return False, err


async def dispatch_video_to_targets(
    post_id: int,
    target_ids: List[int],
    video_rel_path: Optional[str] = None,
    script_data: Optional[Dict[str, Any]] = None,
    video_path: Optional[Any] = None,
    *args,
    **kwargs
) -> List[Dict[str, Any]]:
    db = SessionLocal()
    results = []
    try:
        data_root = settings.DATA_ROOT_PATH or settings.data_dir
        rel_str = str(video_path or video_rel_path or "")
        video_abs = data_root / rel_str
        if not video_abs.is_file():
            p2 = Path(rel_str)
            if p2.is_file():
                video_abs = p2
            else:
                return [{"status": "failed", "error": f"Không tìm thấy file video: {rel_str}"}]

        post = db.query(RawPost).filter_by(id=post_id).first()
        if not post:
            return [{"status": "failed", "error": "Không tìm thấy bài viết"}]

        targets = db.query(PublishTarget).filter(PublishTarget.id.in_(target_ids), PublishTarget.is_active.is_(True)).all()
        for t in targets:
            plat = (t.platform or "").lower()
            if plat == "telegram":
                ok, msg = await publish_video_to_telegram(post, t, str(video_abs), script_data, db)
                results.append({"platform": "telegram", "target_id": t.id, "ok": ok, "message": msg})
            elif plat == "facebook":
                ok, msg = await publish_video_to_facebook(post, t, str(video_abs), script_data, db)
                results.append({"platform": "facebook", "target_id": t.id, "ok": ok, "message": msg})
            elif plat == "youtube":
                # Package YouTube Shorts ready info
                pub_url = "https://studio.youtube.com"
                db.add(PublishLog(
                    raw_post_id=post.id,
                    publish_target_id=t.id,
                    status="success",
                    platform_post_id="youtube_shorts_ready",
                    published_url=pub_url
                ))
                db.commit()
                results.append({"platform": "youtube", "target_id": t.id, "ok": True, "message": "Đã đóng gói YouTube Shorts."})
            else:
                msg = f"Nền tảng '{plat}' chưa được hỗ trợ."
                db.add(PublishLog(
                    raw_post_id=post.id,
                    publish_target_id=t.id,
                    status="failed",
                    error_message=msg
                ))
                db.commit()
                results.append({"platform": plat, "target_id": t.id, "ok": False, "message": msg})
    finally:
        db.close()
    return results
