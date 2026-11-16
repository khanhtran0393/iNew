import re
import hashlib
from typing import Tuple, Optional, NamedTuple
from rapidfuzz import fuzz
from app.database import SessionLocal
from app.models import RawPost
from app.config import settings


class DeduplicationResult(NamedTuple):
    is_duplicate: bool
    original_post_id: Optional[int] = None

    def __bool__(self) -> bool:
        return bool(self.is_duplicate)


def normalize_post_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[#@][\w_]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def compute_text_hash(text: str) -> str:
    norm = normalize_post_text(text)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def check_deduplication(*args, **kwargs) -> Tuple[bool, Optional[int]]:
    """Flexible deduplication check supporting both signatures:
    1. check_deduplication(text, current_post_id=None)
    2. check_deduplication(db, text, current_post_id_or_topic=None)
    """
    db_passed = None
    text = ""
    current_post_id = kwargs.get("current_post_id")

    if args:
        if isinstance(args[0], str):
            text = args[0]
            if len(args) > 1 and isinstance(args[1], int):
                current_post_id = args[1]
        else:
            db_passed = args[0]
            if len(args) > 1 and isinstance(args[1], str):
                text = args[1]
            if len(args) > 2 and isinstance(args[2], int):
                current_post_id = args[2]

    if not text:
        text = kwargs.get("text", "")

    if not text:
        return DeduplicationResult(False, None)

    h = compute_text_hash(text)
    db = db_passed if db_passed is not None else SessionLocal()
    close_db = (db_passed is None)
    try:
        exact = db.query(RawPost).filter(RawPost.text_hash == h).first()
        if exact and exact.id != current_post_id:
            return DeduplicationResult(True, exact.id)

        norm = normalize_post_text(text)
        if len(norm) > 50 and settings.ENABLE_SEMANTIC_DEDUP:
            recent_posts = (
                db.query(RawPost.id, RawPost.original_text)
                .order_by(RawPost.created_at.desc())
                .limit(200)
                .all()
            )
            for pid, rtext in recent_posts:
                if pid == current_post_id or not rtext:
                    continue
                rnorm = normalize_post_text(rtext)
                ratio = fuzz.ratio(norm, rnorm)
                if ratio >= settings.DEDUP_FUZZY_THRESHOLD:
                    return DeduplicationResult(True, pid)
        return DeduplicationResult(False, None)
    finally:
        if close_db:
            db.close()
