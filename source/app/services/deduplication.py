"""Fuzzy and exact deduplication for incoming articles and news."""

import re
import hashlib
from difflib import SequenceMatcher
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from app.models import RawPost, RawPostStatus
from app.config import settings


def normalize_text(text: str) -> str:
    t = re.sub(r"https?://\S+", "", text or "")
    t = re.sub(r"\s+", " ", t)
    return t.strip().lower()


def compute_text_hash(text: str) -> str:
    norm = normalize_text(text)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def check_duplicate(db: Session, text: str) -> Tuple[bool, Optional[int], float]:
    h = compute_text_hash(text)
    exact = db.query(RawPost).filter(RawPost.text_hash == h).first()
    if exact:
        return True, exact.id, 1.0

    # Fuzzy check
    norm = normalize_text(text)
    if len(norm) > 50:
        recent = db.query(RawPost).order_by(RawPost.id.desc()).limit(100).all()
        for r in recent:
            if r.normalized_text and len(r.normalized_text) > 50:
                ratio = SequenceMatcher(None, norm[:300], r.normalized_text[:300]).ratio()
                if ratio >= settings.DEDUP_FUZZY_THRESHOLD:
                    return True, r.id, round(ratio, 2)
    return False, None, 0.0
