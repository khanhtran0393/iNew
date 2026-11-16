import os
import re
from typing import List, Tuple, Optional

CODEC_SAMPLES_PER_FRAME = 320
EDGE_FADE_S = 0.05
EDGE_KEEP_S = 0.1
EDGE_THRESH_DB = -40.0
BABBLE_MAX_RETRIES = 3
BABBLE_MAX_SYLLABLES = 100

RE_SENTENCE_END = re.compile(r"([.!?;]+[\s\n]+)")
RE_NEWLINE = re.compile(r"\n+")
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
