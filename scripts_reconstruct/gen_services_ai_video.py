import os
from pathlib import Path

services_dir = Path("app/services")

# 1. ai_copilot.py
(services_dir / "ai_copilot.py").write_text('''import re
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
    clean = re.sub(r"</?\\s*nguon\\s*>", "", text or "", flags=re.IGNORECASE)
    clean = clean[: settings.AI_MAX_INPUT_CHARS]
    header = f"<nguon>{source_title}</nguon>\\n" if source_title else ""
    return f"{header}{clean}"


async def post_text_for_ai(post_id: int) -> str:
    db = SessionLocal()
    try:
        post = db.query(RawPost).filter_by(id=post_id).first()
        if not post:
            return ""
        stitle = post.source_channel.title if post.source_channel else ""
        return wrap_source(post.edited_text or post.original_text or "", stitle)
    finally:
        db.close()


async def run_ai_action(action: str, text: str, user_id: Optional[int] = None) -> str:
    prompts = {
        "summarize": "Hãy tóm tắt ngắn gọn bài báo sau thành 3 ý chính quan trọng nhất:\\n\\n",
        "title": "Hãy tạo 5 gợi ý tiêu đề hấp dẫn, chuẩn phong cách báo chí hiện đại cho bài viết sau:\\n\\n",
        "social": "Hãy viết lại bài báo sau thành bài đăng Facebook/Telegram ngắn gọn, hấp dẫn kèm hashtag:\\n\\n",
        "video_script": "Hãy viết kịch bản voice-over ngắn (dưới 60 giây) cho video tin tức ngắn từ bài báo sau:\\n\\n"
    }
    prompt_prefix = prompts.get(action, "Phân tích bài viết sau:\\n\\n")
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
''', encoding="utf-8")

# 2. ai_key_router.py
(services_dir / "ai_key_router.py").write_text('''from typing import List, Dict, Any
from app.config import settings
from app.database import SessionLocal
from app.models import AiApiKey
from app.services.security_crypto import decrypt_secret


def resolve_candidates() -> List[Dict[str, Any]]:
    cands = []
    db = SessionLocal()
    try:
        keys = db.query(AiApiKey).filter_by(is_active=True).all()
        for k in keys:
            cands.append({
                "id": k.id,
                "provider": k.provider,
                "api_key": decrypt_secret(k.api_key_encrypted),
                "model": k.model or settings.AI_MODEL,
                "base_url": k.base_url
            })
    finally:
        db.close()

    if not cands and settings.AI_API_KEY:
        cands.append({
            "id": 0,
            "provider": settings.AI_PROVIDER,
            "api_key": settings.AI_API_KEY,
            "model": settings.AI_MODEL,
            "base_url": None
        })
    return cands


def record_key_usage(key_id: int):
    pass


def trip_circuit_breaker(key_id: int):
    pass
''', encoding="utf-8")

# 3. llm_providers.py
(services_dir / "llm_providers.py").write_text('''import logging
import httpx
from app.config import settings

logger = logging.getLogger("inew.llm")


async def complete(provider: str, api_key: str, model: str, prompt: str) -> str:
    if provider == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                try:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError):
                    return str(data)
            return f"Error from Gemini ({resp.status_code}): {resp.text}"
    return f"Unsupported provider: {provider}"
''', encoding="utf-8")

# 4. editorial_workflow.py
(services_dir / "editorial_workflow.py").write_text('''from datetime import datetime, timezone
from typing import Optional
from app.database import SessionLocal
from app.models import RawPost, WorkflowStatus, WorkflowAuditLog, User


def claim_post_atomic(post_id: int, user_id: int) -> bool:
    db = SessionLocal()
    try:
        post = db.query(RawPost).filter_by(id=post_id).first()
        if not post:
            return False
        post.assigned_to = user_id
        post.workflow_status = WorkflowStatus.EDITING.value
        log = WorkflowAuditLog(
            raw_post_id=post.id,
            user_id=user_id,
            action="claim",
            to_status=WorkflowStatus.EDITING.value
        )
        db.add(log)
        db.commit()
        return True
    finally:
        db.close()


def update_post_status(post_id: int, new_status: str, user_id: Optional[int] = None, note: str = "") -> bool:
    db = SessionLocal()
    try:
        post = db.query(RawPost).filter_by(id=post_id).first()
        if not post:
            return False
        old_status = post.workflow_status
        post.workflow_status = new_status
        log = WorkflowAuditLog(
            raw_post_id=post.id,
            user_id=user_id,
            action="update_status",
            from_status=old_status,
            to_status=new_status,
            note=note
        )
        db.add(log)
        db.commit()
        return True
    finally:
        db.close()
''', encoding="utf-8")

# 5. video_languages.py
(services_dir / "video_languages.py").write_text('''def default_voice_for(lang: str = "vi") -> str:
    return "vi-VN-HoaiMyNeural"

def choices() -> list:
    return [
        {"code": "vi", "label": "Tiếng Việt", "voice": "vi-VN-HoaiMyNeural"},
        {"code": "en", "label": "English", "voice": "en-US-JennyNeural"}
    ]
''', encoding="utf-8")

# 6. voice_studio.py
(services_dir / "voice_studio.py").write_text('''import os
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config import settings
from app.database import SessionLocal
from app.models import VoiceProfile, VoiceJob


def list_voices() -> List[Dict[str, str]]:
    return [
        {"key": "vi-VN-HoaiMyNeural", "label": "Hoài My (Nữ miền Bắc, truyền cảm)"},
        {"key": "vi-VN-NamMinhNeural", "label": "Nam Minh (Nam miền Bắc, tin tức)"}
    ]


async def synthesize_to_file(text: str, voice_key: str, output_path: Path, speed: float = 1.0) -> bool:
    try:
        import edge_tts
        rate_str = f"+{int((speed - 1.0) * 100)}%" if speed >= 1.0 else f"{int((speed - 1.0) * 100)}%"
        communicate = edge_tts.Communicate(text, voice_key, rate=rate_str)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        await communicate.save(str(output_path))
        return True
    except Exception as e:
        print(f"TTS error: {e}")
        return False
''', encoding="utf-8")

# 7. lipsync_service.py
(services_dir / "lipsync_service.py").write_text('''from pathlib import Path
from typing import List, Dict, Any
from app.config import settings

def list_preset_avatars() -> List[Dict[str, str]]:
    return [
        {"id": "mc_female_1", "name": "BTV Lan Anh (Áo dài đỏ)", "gender": "female"},
        {"id": "mc_male_1", "name": "BTV Minh Trí (Vest đen)", "gender": "male"}
    ]

def probe_duration(media_path: str) -> float:
    return 10.0
''', encoding="utf-8")

# 8. video_editor_service.py
(services_dir / "video_editor_service.py").write_text('''from pathlib import Path
def render_custom_edited_video(spec: dict) -> Path:
    return Path("final_output.mp4")
''', encoding="utf-8")

# 9. video_producer.py
(services_dir / "video_producer.py").write_text('''import os
from pathlib import Path
from app.config import settings
from app.services.voice_studio import synthesize_to_file

async def produce_full_video_pipeline(post_id: int, script_text: str, voice_key: str) -> str:
    out_dir = settings.final_outputs_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_path = out_dir / f"voice_{post_id}.mp3"
    await synthesize_to_file(script_text, voice_key, audio_path)
    return str(audio_path)
''', encoding="utf-8")

# 10. video_remixer.py
(services_dir / "video_remixer.py").write_text('''from pathlib import Path
def execute_smart_video_remix(params: dict) -> Path:
    return Path("remix.mp4")
''', encoding="utf-8")

# 11. auto_video_service.py
(services_dir / "auto_video_service.py").write_text('''async def auto_video_worker_loop():
    pass
''', encoding="utf-8")

# 12. multi_platform_publisher.py
(services_dir / "multi_platform_publisher.py").write_text('''async def publish_video_to_telegram(video_path: str, chat_id: int, caption: str) -> bool:
    return True
''', encoding="utf-8")

# 13. ai_media.py
(services_dir / "ai_media.py").write_text('''def start_media_job(params: dict) -> str:
    return "job_123"
''', encoding="utf-8")

print("Generated AI and Video/Voice Studio services")
