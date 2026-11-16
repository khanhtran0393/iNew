import logging
from typing import Optional, Dict, Any, List
import httpx

from app.config import settings

logger = logging.getLogger("ak_news.llm")

GEMINI_ROOT = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_THINKING_LEVEL = 1
GEMINI_THINKING_HEADROOM = 1000

PROVIDERS: List[Dict[str, str]] = [
    {"id": "gemini", "name": "Google Gemini", "default_model": "gemini-1.5-flash"},
    {"id": "openai", "name": "OpenAI (ChatGPT)", "default_model": "gpt-4o-mini"},
    {"id": "anthropic", "name": "Anthropic Claude", "default_model": "claude-3-5-sonnet-20241022"},
    {"id": "deepseek", "name": "DeepSeek", "default_model": "deepseek-chat"},
]


class LLMError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

    def __str__(self):
        if self.status_code:
            return f"[HTTP {self.status_code}] {self.message}"
        return self.message


def http_client(timeout: float = 45.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout)


async def complete(
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    if not provider or not api_key:
        try:
            from app.services.ai_key_router import resolve_candidates
            cands = resolve_candidates()
            if cands:
                provider = provider or cands[0].get("provider")
                api_key = api_key or cands[0].get("api_key")
                model = model or cands[0].get("model")
        except Exception:
            pass

    provider = provider or settings.AI_PROVIDER or "gemini"
    api_key = api_key or settings.AI_API_KEY or ""
    model = model or settings.AI_MODEL or "gemini-2.5-flash"

    if not api_key:
        return "Chưa cấu hình API Key AI trong hệ thống. Vui lòng vào Cài đặt AI để thêm key."

    prov = (provider or "gemini").lower()

    if prov == "gemini":
        url = f"{GEMINI_ROOT}/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }
        async with http_client() as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                try:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError) as e:
                    raise LLMError(f"Malformed Gemini response: {data}") from e
            raise LLMError(f"Gemini API returned error: {resp.text}", status_code=resp.status_code)

    elif prov in ("openai", "deepseek"):
        base_url = "https://api.openai.com/v1" if prov == "openai" else "https://api.deepseek.com/v1"
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        async with http_client() as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                try:
                    return data["choices"][0]["message"]["content"]
                except (KeyError, IndexError) as e:
                    raise LLMError(f"Malformed {prov} response: {data}") from e
            raise LLMError(f"{prov.upper()} API returned error: {resp.text}", status_code=resp.status_code)

    elif prov == "anthropic":
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        async with http_client() as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                try:
                    return data["content"][0]["text"]
                except (KeyError, IndexError) as e:
                    raise LLMError(f"Malformed Anthropic response: {data}") from e
            raise LLMError(f"Anthropic API returned error: {resp.text}", status_code=resp.status_code)

    raise LLMError(f"Unsupported LLM provider: {prov}")
