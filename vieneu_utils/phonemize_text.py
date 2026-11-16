import re
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
