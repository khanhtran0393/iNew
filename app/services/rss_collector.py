import re
import logging
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
import httpx
from app.database import SessionLocal
from app.models import SourceChannel, RawPost, RawPostStatus, WorkflowStatus
from app.services.deduplication import check_deduplication, compute_text_hash

logger = logging.getLogger("inew.rss")


def clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    clean = re.sub(r"<[^>]+>", " ", raw_html)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()


def parse_feed_items(xml_content: str):
    items = []
    try:
        root = ET.fromstring(xml_content)
        # Handle RSS 2.0
        for item in root.findall(".//item"):
            title = item.findtext("title") or ""
            link = item.findtext("link") or ""
            description = item.findtext("description") or ""
            pub_date = item.findtext("pubDate") or ""
            items.append({
                "title": clean_html(title),
                "link": link.strip(),
                "description": clean_html(description),
                "pub_date": pub_date
            })
    except Exception as e:
        logger.error(f"Error parsing RSS XML: {e}")
    return items


def fetch_and_ingest_rss(source: SourceChannel) -> int:
    if not source.rss_url:
        return 0
    new_count = 0
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            resp = client.get(source.rss_url)
            if resp.status_code != 200:
                logger.warning(f"Failed to fetch RSS {source.title}: HTTP {resp.status_code}")
                return 0
            items = parse_feed_items(resp.text)
    except Exception as e:
        logger.error(f"Error fetching RSS {source.rss_url}: {e}")
        return 0

    db = SessionLocal()
    try:
        for it in items:
            title = it["title"]
            desc = it["description"]
            text_content = f"{title}\n\n{desc}".strip()
            if not text_content:
                continue

            # Check duplicate
            is_dup, _ = check_deduplication(text_content)
            if is_dup:
                continue

            h = compute_text_hash(text_content)
            post = RawPost(
                source_channel_id=source.id,
                source_url=it["link"],
                title=title,
                original_text=text_content,
                text_hash=h,
                status=RawPostStatus.NEW.value,
                workflow_status=WorkflowStatus.CLAIMED.value,
                created_at=datetime.now(timezone.utc)
            )
            db.add(post)
            new_count += 1
        db.commit()
    finally:
        db.close()
    return new_count


def sync_all_rss_sources() -> int:
    db = SessionLocal()
    try:
        sources = db.query(SourceChannel).filter_by(source_type="rss", is_active=True).all()
        total_new = 0
        for s in sources:
            total_new += fetch_and_ingest_rss(s)
        return total_new
    finally:
        db.close()


def stable_message_id(url: str, guid: str = "") -> int:
    import hashlib
    key = (guid or url or "").strip()
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(h[:8], 16) & 0x7FFFFFFF
