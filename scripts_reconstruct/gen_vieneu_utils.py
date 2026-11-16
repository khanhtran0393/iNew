from pathlib import Path

pkg_dir = Path("vieneu_utils")
pkg_dir.mkdir(exist_ok=True)

# 1. vieneu_utils/core_utils.py
(pkg_dir / "core_utils.py").write_text('''import os
import re
from typing import List, Tuple, Optional

CODEC_SAMPLES_PER_FRAME = 320
EDGE_FADE_S = 0.05
EDGE_KEEP_S = 0.1
EDGE_THRESH_DB = -40.0
BABBLE_MAX_RETRIES = 3
BABBLE_MAX_SYLLABLES = 100

RE_SENTENCE_END = re.compile(r"([.!?;]+[\s\\n]+)")
RE_NEWLINE = re.compile(r"\\n+")
RE_MINOR_PUNCT = re.compile(r"([,:])")


def split_into_sentences(text: str) -> List[str]:
    if not text:
        return []
    parts = RE_SENTENCE_END.split(text)
    sentences = []
    current = ""
    for p in parts:
        current += p
        if RE_SENTENCE_END.search(p):
            if current.strip():
                sentences.append(current.strip())
            current = ""
    if current.strip():
        sentences.append(current.strip())
    return sentences


def split_text_into_chunks(text: str, max_chars: int = 150) -> List[str]:
    sentences = split_into_sentences(text)
    chunks = []
    current = ""
    for s in sentences:
        if len(current) + len(s) + 1 <= max_chars:
            current = f"{current} {s}".strip() if current else s
        else:
            if current:
                chunks.append(current)
            if len(s) > max_chars:
                words = s.split()
                sub = ""
                for w in words:
                    if len(sub) + len(w) + 1 <= max_chars:
                        sub = f"{sub} {w}".strip() if sub else w
                    else:
                        if sub:
                            chunks.append(sub)
                        sub = w
                if sub:
                    chunks.append(sub)
                current = ""
            else:
                current = s
    if current:
        chunks.append(current)
    return chunks


def is_cue_only(text: str) -> bool:
    return bool(re.match(r"^<\|emotion_[^>|]+\|>$", text.strip()))


def join_audio_chunks(chunks: List[bytes], crossfade_ms: int = 20) -> bytes:
    if not chunks:
        return b""
    return b"".join(chunks)


def syllable_count(text: str) -> int:
    return len(text.split())
''', encoding="utf-8")

# 2. vieneu_utils/phonemize_text.py
(pkg_dir / "phonemize_text.py").write_text('''import re
from typing import List, Dict, Any, Optional
from sea_g2p import SEAPipeline, Normalizer, G2P
from .core_utils import split_text_into_chunks

_pipeline: Optional[SEAPipeline] = None


def _get_pipeline() -> SEAPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = SEAPipeline(lang="vi")
    return _pipeline


def phonemize_text(text: str, punc_norm: bool = True) -> str:
    if not text:
        return ""
    p = _get_pipeline()
    res = p.run(text, punc_norm=punc_norm)
    return res.get("phonemes", text)


def phonemize_text_with_emotions(text: str, punc_norm: bool = True) -> str:
    # Preserve emotion tags like <|emotion_happy|>
    parts = re.split(r"(<\|emotion_[^>|]+\|>)", text)
    out = []
    for p in parts:
        if p.startswith("<|emotion_") and p.endswith("|>"):
            out.append(p)
        else:
            out.append(phonemize_text(p, punc_norm=punc_norm))
    return "".join(out)


def normalize_to_chunks(text: str, max_chars: int = 150) -> List[str]:
    return split_text_into_chunks(text, max_chars=max_chars)


def phonemize_to_chunks(text: str, max_chars: int = 150) -> List[Dict[str, str]]:
    chunks = normalize_to_chunks(text, max_chars=max_chars)
    results = []
    for c in chunks:
        ph = phonemize_text_with_emotions(c)
        results.append({"text": c, "phonemes": ph})
    return results
''', encoding="utf-8")

# 3. vieneu_utils/url_extract.py
(pkg_dir / "url_extract.py").write_text('''import json
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
''', encoding="utf-8")

# 4. vieneu_utils/__init__.py
(pkg_dir / "__init__.py").write_text('''"""VieNeu Utility Package."""
from .core_utils import split_into_sentences, split_text_into_chunks, join_audio_chunks
from .phonemize_text import phonemize_text, phonemize_to_chunks
from .url_extract import extract_text_from_url

__all__ = [
    "split_into_sentences",
    "split_text_into_chunks",
    "join_audio_chunks",
    "phonemize_text",
    "phonemize_to_chunks",
    "extract_text_from_url"
]
''', encoding="utf-8")

print("Generated vieneu_utils package (4 files)")
