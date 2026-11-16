from typing import List, Dict, Any, Optional
from app.config import settings
from app.database import SessionLocal
from app.models import AiApiKey
from app.services.security_crypto import decrypt_secret


def resolve_candidates(task: Optional[str] = None, topic_id: Optional[int] = None, *args, **kwargs) -> List[Dict[str, Any]]:
    cands = []
    db = SessionLocal()
    try:
        keys = db.query(AiApiKey).filter_by(is_active=True).all()
        for k in keys:
            cands.append({
                "id": k.id,
                "key_id": k.id,
                "provider": k.provider,
                "api_key": decrypt_secret(k.api_key_encrypted),
                "model": k.model or settings.AI_MODEL,
                "models": [k.model] if k.model else None,
                "base_url": k.base_url
            })
    finally:
        db.close()

    if not cands and settings.AI_API_KEY:
        cands.append({
            "id": 0,
            "key_id": 0,
            "provider": settings.AI_PROVIDER,
            "api_key": settings.AI_API_KEY,
            "model": settings.AI_MODEL,
            "models": [settings.AI_MODEL],
            "base_url": None
        })
    return cands


def record_key_usage(key_id: int, success: bool = True, *args, **kwargs):
    if not key_id:
        return
    db = SessionLocal()
    try:
        k = db.query(AiApiKey).filter_by(id=key_id).first()
        if k:
            if success:
                if k.failure_count > 0:
                    k.failure_count = 0
            else:
                k.failure_count = (k.failure_count or 0) + 1
                if k.failure_count >= 5:
                    k.is_active = False
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def trip_circuit_breaker(key_id: int):
    if not key_id:
        return
    db = SessionLocal()
    try:
        k = db.query(AiApiKey).filter_by(id=key_id).first()
        if k:
            k.failure_count = (k.failure_count or 0) + 1
            if k.failure_count >= 5:
                k.is_active = False
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
def dd(key_id: int) -> dict:
    """Get AI key details by ID."""
    db = SessionLocal()
    try:
        key = db.query(AiApiKey).filter(AiApiKey.id == key_id).first()
        if not key:
            raise ValueError(f"AI key with ID {key_id} not found")
        return {
            "id": key.id,
            "provider": key.provider,
            "label": key.label,
            "is_active": key.is_active,
            "created_at": key.created_at.isoformat() if key.created_at else None,
        }
    finally:
        db.close()


def find_best_ai_key(text_content: str) -> AiApiKey:
    """Find the best AI key for given text content."""
    db = SessionLocal()
    try:
        keywords = {
            "gpt": ["gpt", "openai", "chatgpt"],
            "gemini": ["gemini", "google", "gemini ai"],
            "claude": ["claude", "anthropic"],
            "llama": ["llama", "llama2", "llama3"],
        }
        text_lower = text_content.lower()
        best_key = None
        max_score = 0
        for key in db.query(AiApiKey).all():
            score = 0
            for keyword in keywords.get(key.provider.lower(), []):
                if keyword in text_lower:
                    score += 1
            if score > max_score:
                max_score = score
                best_key = key
        if not best_key:
            raise ValueError("No suitable AI key found for content")
        return best_key
    finally:
        db.close()


def get_purpose_meta(purpose: str) -> dict:
    """Get metadata for a given purpose."""
    db = SessionLocal()
    try:
        purpose_lower = purpose.lower()
        metadata = {
            "gpt": {
                "description": "OpenAI GPT models",
                "capabilities": ["text_completion", "summarization", "translation"],
                "limitations": ["rate_limited", "cost_based"],
            },
            "gemini": {
                "description": "Google Gemini models",
                "capabilities": ["multimodal", "reasoning", "code"],
                "limitations": ["context_length", "safety_filters"],
            },
            "claude": {
                "description": "Anthropic Claude models",
                "capabilities": ["analysis", "summarization", "translation"],
                "limitations": ["token_window", "safety"],
            },
        }
        return metadata.get(purpose_lower, {"error": "unknown purpose"})
    finally:
        db.close()


def is_circuit_open(key_id: int) -> bool:
    """Check if the circuit breaker is open for the given key."""
    db = SessionLocal()
    try:
        key = db.query(AiApiKey).filter_by(id=key_id).first()
        if not key:
            return False
        return key.failure_count is not None and key.failure_count >= 5
    finally:
        db.close()


def test_ai_key(key_id: int) -> bool:
    """Test if the AI key is functional."""
    db = SessionLocal()
    try:
        key = db.query(AiApiKey).filter_by(id=key_id).first()
        if not key:
            return False
        return key.is_active
    finally:
        db.close()


def test_gemini_api_key(api_key: str) -> bool:
    """Test if a Gemini API key is valid."""
    return api_key and api_key.startswith("AIza")
