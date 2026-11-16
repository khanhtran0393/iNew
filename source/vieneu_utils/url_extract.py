"""URL and link extraction utility for TTS sanitization."""

import re
from typing import List


def extract_urls(text: str) -> List[str]:
    return re.findall(r"https?://\S+", text or "")


def strip_urls(text: str) -> str:
    return re.sub(r"https?://\S+", "", text or "")
