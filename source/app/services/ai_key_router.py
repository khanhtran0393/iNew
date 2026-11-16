"""AI API key selection and rotation router."""

from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models import AiApiKey, AiTaskRoute
from app.config import settings


def get_active_ai_key(db: Session, task: str = "editorial") -> Tuple[str, str, str]:
    """Return (api_key, model, provider)."""
    route = db.query(AiTaskRoute).filter(AiTaskRoute.task == task).first()
    if route and route.ai_key and route.ai_key.api_key:
        return route.ai_key.api_key, route.ai_key.model, route.ai_key.provider

    key_record = db.query(AiApiKey).filter(AiApiKey.provider == "gemini").order_by(AiApiKey.id.asc()).first()
    if key_record and key_record.api_key:
        return key_record.api_key, key_record.model, key_record.provider

    # Fallback to .env configuration
    return settings.AI_API_KEY, settings.AI_MODEL, settings.AI_PROVIDER
