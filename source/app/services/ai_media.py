"""Multimodal vision and media understanding with Gemini."""

from typing import Optional
from sqlalchemy.orm import Session
from app.services.ai_key_router import get_active_ai_key


async def analyze_image_content(db: Session, image_bytes: bytes) -> Optional[str]:
    # Vision analysis placeholder
    return "Hình ảnh báo chí minh họa tin tức"
