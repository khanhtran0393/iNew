import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from app.config import settings
from app.database import SessionLocal
from app.models import AiUsageLog, RawPost
from app.services.ai_key_router import resolve_candidates, record_key_usage, trip_circuit_breaker
from app.services.llm_providers import complete

logger = logging.getLogger("inew.ai_copilot")


def _vn_day_start_utc() -> datetime:
    now_vn = datetime.now(timezone.utc) + timedelta(hours=7)
    start_vn = now_vn.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_vn - timedelta(hours=7)


def ai_usage_today(user_id: Optional[int] = None) -> Dict[str, int]:
    start = _vn_day_start_utc()
    db = SessionLocal()
    try:
        total = db.query(AiUsageLog).filter(AiUsageLog.created_at >= start).count()
        mine = 0
        if user_id:
            mine = (
                db.query(AiUsageLog)
                .filter(AiUsageLog.created_at >= start, AiUsageLog.user_id == user_id)
                .count()
            )
        return {"total": total, "mine": mine}
    finally:
        db.close()


def wrap_source(text: str, source_title: str) -> str:
    clean = re.sub(r"</?\s*nguon\s*>", "", text or "", flags=re.IGNORECASE)
    clean = clean[: settings.AI_MAX_INPUT_CHARS]
    header = f"<nguon>{source_title}</nguon>\n" if source_title else ""
    return f"{header}{clean}"


async def post_text_for_ai(post_id: int) -> str:
    db = SessionLocal()
    try:
        post = db.query(RawPost).filter_by(id=post_id).first()
        if not post:
            return ""
        stitle = post.source_channel.title if post.source_channel else ""
        content = post.resolved_text or post.title or ""
        return wrap_source(content, stitle)
    finally:
        db.close()


async def run_ai_action(action: str, text: str, user_id: Optional[int] = None) -> str:
    prompts = {
        "summarize": "Hãy tóm tắt ngắn gọn bài báo sau thành 3 ý chính quan trọng nhất:\n\n",
        "title": "Hãy tạo 5 gợi ý tiêu đề hấp dẫn, chuẩn phong cách báo chí hiện đại cho bài viết sau:\n\n",
        "social": "Hãy viết lại bài báo sau thành bài đăng Facebook/Telegram ngắn gọn, hấp dẫn kèm hashtag:\n\n",
        "video_script": "Hãy viết kịch bản voice-over ngắn (dưới 60 giây) cho video tin tức ngắn từ bài báo sau:\n\n"
    }
    prompt_prefix = prompts.get(action, "Phân tích bài viết sau:\n\n")
    candidates = resolve_candidates()
    if not candidates:
        return "Chưa cấu hình API key AI. Vui lòng vào mục Cài đặt AI để thêm key."

    cand = candidates[0]
    res = await complete(
        provider=cand["provider"],
        api_key=cand["api_key"],
        model=cand["model"],
        prompt=f"{prompt_prefix}{text}"
    )
    return res
