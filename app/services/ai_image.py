import os
import re
import json
import base64
import logging
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import httpx
import urllib.parse

from app.config import settings
from app.services.ai_key_router import resolve_candidates, record_key_usage
from app.services.llm_providers import GEMINI_ROOT, LLMError, http_client
from app.services.security_crypto import decrypt_secret

logger = logging.getLogger("ak_news.ai_image")

TASK = "image_gen"
IMAGE_PROVIDERS = ("gemini", "openai", "pollinations")
DEFAULT_MODELS = {
    "gemini": ["gemini-nano-banana-2.1", "gemini-3.1-flash-lite-image", "gemini-3.1-flash-image"],
    "openai": ["gpt-image-2", "gpt-image-1.5", "gpt-image-1-mini"],
    "pollinations": ["black-forest-labs/FLUX.1-schnell", "black-forest-labs/FLUX.1-dev"]
}
GEMINI_API_REVISION = "2026-05-20"
ASPECTS = ("9:16", "16:9", "1:1", "4:5", "3:4", "4:3")
TIMEOUT_S = 60
PROMPT_SUFFIX = "\n\nYêu cầu: ảnh minh hoạ cho bản tin video, không chứa chữ, không logo, không watermark, không vẽ khuôn mặt nhận ra được của người thật."


class ImageAIError(Exception):
    pass


def is_image_model(name: str) -> bool:
    name_l = name.lower()
    return any(k in name_l for k in ("image", "imagen", "banana", "dall-e", "flux"))


def _refusal(text: str) -> bool:
    t = text.upper()
    return any(p in t for p in ("IMAGE_SAFETY", "PROHIBITED_CONTENT", "SAFETY", "BLOCKED", "CONTENT_POLICY"))


async def _gemini(client: httpx.AsyncClient, api_key: str, model: str, prompt: str, aspect: str) -> bytes:
    url = f"{GEMINI_ROOT}/v1beta/models/{model}:generateContent"
    headers = {
        "x-goog-api-key": api_key,
        "Api-Revision": GEMINI_API_REVISION
    }
    body = {
        "contents": [{"parts": [{"text": prompt + PROMPT_SUFFIX}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": aspect}
        }
    }
    resp = await client.post(url, headers=headers, json=body, timeout=TIMEOUT_S)
    if resp.status_code != 200:
        if _refusal(resp.text):
            raise ImageAIError("AI từ chối vẽ ảnh này (bộ lọc an toàn của Google). Hãy đổi mô tả.")
        raise LLMError(f"Gemini error {resp.status_code}: {resp.text}")

    data = resp.json()
    # Find inline image data
    candidates = data.get("candidates", [])
    for c in candidates:
        parts = c.get("content", {}).get("parts", [])
        for p in parts:
            inline = p.get("inlineData") or p.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
    raise LLMError("Gemini không trả về ảnh.")


async def _openai(client: httpx.AsyncClient, api_key: str, model: str, prompt: str, aspect: str, base_url: str = "") -> bytes:
    root = (base_url or "https://api.openai.com/v1").rstrip("/")
    url = f"{root}/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    size_map = {
        "9:16": "1024x1536",
        "16:9": "1536x1024",
        "1:1": "1024x1024"
    }
    size = size_map.get(aspect, "1024x1024")
    body = {
        "model": model,
        "prompt": prompt + PROMPT_SUFFIX,
        "size": size,
        "n": 1,
        "response_format": "b64_json"
    }
    resp = await client.post(url, headers=headers, json=body, timeout=TIMEOUT_S)
    if resp.status_code != 200:
        if _refusal(resp.text):
            raise ImageAIError("AI từ chối vẽ ảnh này (bộ lọc an toàn của OpenAI). Hãy đổi mô tả.")
        raise LLMError(f"OpenAI error {resp.status_code}: {resp.text}")

    data = resp.json()
    items = data.get("data", [])
    if items and items[0].get("b64_json"):
        return base64.b64decode(items[0]["b64_json"])
    raise LLMError("OpenAI không trả về ảnh.")


async def _pollinations(client: httpx.AsyncClient, api_key: str, model: str, prompt: str, aspect: str, base_url: str = "") -> bytes:
    url = f"{base_url or 'https://api.pollinations.ai/v1'}/images/generations"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    # Map aspect ratios to Pollinations format
    aspect_map = {
        "9:16": "9:16",
        "16:9": "16:9",
        "1:1": "1:1",
        "4:5": "4:5",
        "3:4": "3:4",
        "4:3": "4:3"
    }
    payload = {
        "prompt": prompt + PROMPT_SUFFIX,
        "model": model,
        "aspect_ratio": aspect_map.get(aspect, "9:16"),
        "width": 1024,
        "height": 1024,
        "n": 1,
        "response_format": "b64_json"
    }
    resp = await client.post(url, headers=headers, json=payload, timeout=TIMEOUT_S)
    if resp.status_code != 200:
        if _refusal(resp.text):
            raise ImageAIError("AI từ chối vẽ ảnh này (bộ lọc an toàn của Pollinations). Hãy đổi mô tả.")
        raise LLMError(f"Pollinations error {resp.status_code}: {resp.text}")
    
    data = resp.json()
    items = data.get("data", [])
    if items and items[0].get("b64_json"):
        return base64.b64decode(items[0]["b64_json"])
    raise LLMError("Pollinations không trả về ảnh.")


async def generate(prompt: str, aspect: str = "9:16", topic_id: Optional[int] = None) -> bytes:
    prompt = prompt.strip()
    if not prompt:
        raise ImageAIError("Hãy mô tả ảnh cần tạo.")
    if aspect not in ASPECTS:
        aspect = "9:16"

    candidates = resolve_candidates(TASK, topic_id=topic_id)
    if not candidates:
        # Fallback to general AI keys
        if settings.GEMINI_API_KEY:
            candidates.append({
                "key_id": 0,
                "provider": "gemini",
                "api_key": settings.GEMINI_API_KEY,
                "models": DEFAULT_MODELS["gemini"],
                "base_url": ""
            })
        elif settings.OPENAI_API_KEY:
            candidates.append({
                "key_id": 0,
                "provider": "openai",
                "api_key": settings.OPENAI_API_KEY,
                "models": DEFAULT_MODELS["openai"],
                "base_url": ""
            })
        elif settings.POLLINATIONS_API_KEY:
            candidates.append({
                "key_id": 0,
                "provider": "pollinations",
                "api_key": settings.POLLINATIONS_API_KEY,
                "models": DEFAULT_MODELS["pollinations"],
                "base_url": "https://api.pollinations.ai/v1"
            })

    if not candidates:
        raise ImageAIError("Chưa có tài khoản Google Gemini, OpenAI hoặc Pollinations.ai để tạo ảnh. Admin vào mục Đấu nối AI để thêm.")

    errors = []
    async with http_client() as client:
        for cand in candidates:
            provider = cand.get("provider", "gemini")
            api_key = cand.get("api_key", "")
            base_url = cand.get("base_url", "")
            key_id = cand.get("key_id", 0)
            models = cand.get("models") or DEFAULT_MODELS.get(provider, [])

            for m in models:
                try:
                    logger.info(f"Image model {m} on key #{key_id}")
                    if provider == "gemini":
                        data = await _gemini(client, api_key, m, prompt, aspect)
                    elif provider == "openai":
                        data = await _openai(client, api_key, m, prompt, aspect, base_url)
                    elif provider == "pollinations":
                        data = await _pollinations(client, api_key, m, prompt, aspect, base_url)
                    record_key_usage(key_id, success=True)
                    return data
                except Exception as e:
                    errors.append(f"{m}: {e}")
                    record_key_usage(key_id, success=False)
                    continue

    raise ImageAIError(f"Không tạo được ảnh: {' | '.join(errors[-3:])}")


async def generate_image(prompt: str, output_path: Any, aspect: str = "9:16") -> bool:
    """Generate image and save to disk. Returns True on success."""
    try:
        data = await generate(prompt, aspect=aspect)
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(data)
        return True
    except Exception as e:
        logger.warning(f"generate_image failed: {e}")
        return False
