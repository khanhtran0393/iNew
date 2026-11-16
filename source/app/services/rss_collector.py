"""RSS News ingestion from mainstream Vietnamese newspapers."""

import re
from app.database import SessionLocal
from app.models import SourceChannel, RawPost, RawPostStatus, _utcnow
from app.services.deduplication import check_duplicate, compute_text_hash, normalize_text

VIETNAMESE_NEWS_FEEDS = [
    ("VnExpress - Thời sự", "https://vnexpress.net/rss/thoi-su.rss"),
    ("Tuổi Trẻ - Tin mới", "https://tuoitre.vn/rss/tin-moi-nhat.rss"),
    ("Thanh Niên - Thời sự", "https://thanhnien.vn/rss/thoi-su.rss"),
    ("Dân Trí - Xã hội", "https://dantri.com.vn/rss/xa-hoi.rss"),
]


def clean_html(raw_html: str) -> str:
    clean = re.sub(r"<[^>]+>", "", raw_html or "")
    return re.sub(r"\s+", " ", clean).strip()


def sync_all_vietnamese_news_feeds(limit_per_feed: int = 15) -> dict:
    try:
        import feedparser
    except ImportError:
        return {"total_new": 0, "total_duplicate": 0}

    db = SessionLocal()
    total_new = 0
    total_dup = 0
    try:
        for title, rss_url in VIETNAMESE_NEWS_FEEDS:
            src = db.query(SourceChannel).filter(SourceChannel.rss_url == rss_url).first()
            if not src:
                src = SourceChannel(title=title, source_type="rss", rss_url=rss_url, created_at=_utcnow())
                db.add(src)
                db.commit()
                db.refresh(src)

            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:limit_per_feed]:
                text = f"{entry.get('title', '')}\n\n{clean_html(entry.get('summary', ''))}"
                is_dup, dup_id, score = check_duplicate(db, text)
                if not is_dup:
                    post = RawPost(
                        source_id=src.id,
                        source_url=entry.get("link", ""),
                        original_text=text,
                        normalized_text=normalize_text(text),
                        text_hash=compute_text_hash(text),
                        ingest_method="rss",
                        status=RawPostStatus.READY.value,
                        created_at=_utcnow()
                    )
                    db.add(post)
                    total_new += 1
                else:
                    total_dup += 1
            db.commit()
    finally:
        db.close()
    return {"total_new": total_new, "total_duplicate": total_dup}
