import json
from typing import Dict, Any, Optional
from urllib.parse import urlparse

def extract_text_from_url(url: str, max_chars: int = 10000) -> Dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return {"error": "URL must start with http:// or https://", "text": "", "char_count": 0, "truncated": False}
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return {"error": "Could not download URL", "text": "", "char_count": 0, "truncated": False}
        extracted = trafilatura.extract(downloaded, include_tables=True, include_comments=False) or ""
        truncated = len(extracted) > max_chars
        text = extracted[:max_chars]
        return {
            "error": None,
            "text": text,
            "char_count": len(text),
            "truncated": truncated
        }
    except Exception as e:
        return {"error": str(e), "text": "", "char_count": 0, "truncated": False}
