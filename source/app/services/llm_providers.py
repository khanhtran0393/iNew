"""LLM Providers integration (Gemini, OpenAI, Claude)."""

import aiohttp
from typing import Optional


async def call_gemini(api_key: str, model: str, prompt: str, system_instruction: str = "") -> Optional[str]:
    if not api_key:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    if system_instruction:
        payload["system_instruction"] = {"parts": [{"text": system_instruction}]}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=45) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "")
    except Exception:
        pass
    return None
