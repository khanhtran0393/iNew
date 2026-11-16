"""Vietnamese Phonemizer with emotion tags and punctuation normalization."""

import re
from typing import List, Tuple

_EMOTION_TAG_TO_K = {
    "vui": "<|emotion_happy|>",
    "buồn": "<|emotion_sad|>",
    "giận": "<|emotion_angry|>",
    "ngạc nhiên": "<|emotion_surprised|>",
}


class PuncNormalizer:
    def __init__(self, lang: str = "vi"):
        self.lang = lang

    def normalize(self, text: str) -> str:
        t = re.sub(r'[\"\'“”‘’]', '', text or "")
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    def normalize_batch(self, texts: List[str]) -> List[str]:
        return [self.normalize(t) for t in texts]


def phonemize_text(text: str, punc_norm: bool = True) -> str:
    norm = PuncNormalizer().normalize(text) if punc_norm else text
    try:
        from sea_g2p import G2P
        g2p = G2P(lang="vi")
        return g2p.predict(norm)
    except Exception:
        return norm


def phonemize_text_with_emotions(text: str) -> str:
    parts = re.split(r"(<\|.*?\|>)", text)
    out = []
    for p in parts:
        if p.startswith("<|") and p.endswith("|>"):
            out.append(p)
        else:
            out.append(phonemize_text(p))
    return " ".join(out).strip()


def phonemize_batch(texts: List[str]) -> List[str]:
    return [phonemize_text(t) for t in texts]
