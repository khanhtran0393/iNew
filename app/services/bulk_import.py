import re
import csv
import io
import logging
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import SourceChannel, Topic, TopicSource
from app.services.licensing import channels_remaining
from app.services.source_admin import restore_if_deleted

logger = logging.getLogger("ak_news.bulk_import")

STATUS_ADDED = "ADDED"
STATUS_DUPLICATE = "DUPLICATE"
STATUS_INVALID = "INVALID"
STATUS_REJECTED = "REJECTED"


class BulkImportResult:
    def __init__(self):
        self.total = 0
        self.added = 0
        self.duplicates = 0
        self.invalid = 0
        self.rejected = 0
        self.details: List[Dict[str, Any]] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "added": self.added,
            "duplicates": self.duplicates,
            "invalid": self.invalid,
            "rejected": self.rejected,
            "details": self.details,
        }


def looks_like_feed_url(url: str) -> bool:
    parsed = urlparse(url)
    target = (parsed.path + " " + parsed.query).lower()
    return bool(re.search(r"(\.rss|\.xml|\.atom)$|/rss(/|$)|/feed(/|$)|/feeds?/|rss\.", target))


def parse_telegram_channel_identifier(raw_input: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Returns (clean_url, username, channel_id)"""
    line = raw_input.strip().rstrip("/")
    if not line:
        return None, None, None

    # Clean leading @
    if line.startswith("@"):
        username = line[1:].strip()
        if re.match(r"^[A-Za-z0-9_]{4,64}$", username):
            return f"https://t.me/{username}", username, None

    # Handle t.me/s/ or t.me/
    if re.search(r"(^|//)(www\.)?t\.me/", line, re.IGNORECASE):
        # Match private invite t.me/+ or t.me/joinchat/
        invite_match = re.search(r"t\.me\/(?:joinchat\/|\+)([A-Za-z0-9_-]{8,})", line)
        if invite_match:
            return line, None, None

        # Match private c/ channel
        c_match = re.search(r"t\.me\/c\/(\d+)", line)
        if c_match:
            cid = f"-100{c_match.group(1)}"
            return line, None, cid

        # Match public username
        sub_cleaned = re.sub(r"^https?:\/\/(www\.)?t\.me\/(s\/)?", "", line)
        parts = sub_cleaned.split("/")
        if parts and re.match(r"^[A-Za-z0-9_]{4,64}$", parts[0]):
            username = parts[0]
            return f"https://t.me/{username}", username, None

    # Raw username string
    if re.match(r"^[A-Za-z0-9_]{4,64}$", line):
        return f"https://t.me/{line}", line, None

    return None, None, None


def _import_rss_line(
    db: Session,
    feed_url: str,
    topic_id: Optional[int],
    priority: str,
    result: BulkImportResult
) -> None:
    result.total += 1
    parsed = urlparse(feed_url)
    host = parsed.netloc or "RSS"

    existing = db.query(SourceChannel).filter(SourceChannel.rss_url == feed_url).first()
    if existing:
        if not existing.is_active:
            restore_if_deleted(db, existing.id)
            result.added += 1
            result.details.append({"input": feed_url, "status": STATUS_ADDED, "title": f"{existing.title} (khôi phục)"})
            db.commit()
            return
        result.duplicates += 1
        result.details.append({
            "input": feed_url,
            "status": STATUS_DUPLICATE,
            "reason": f"Đã tồn tại trong hệ thống (ID: {existing.id})",
            "title": existing.title
        })
        return

    rem = channels_remaining(db)
    if rem <= 0:
        result.rejected += 1
        result.details.append({"input": feed_url, "status": STATUS_REJECTED, "reason": "Đạt giới hạn số kênh của bản quyền"})
        return

    title = f"RSS {host}"
    new_source = SourceChannel(
        title=title,
        url=feed_url,
        rss_url=feed_url,
        source_type="rss",
        is_active=True,
        priority=priority.upper() if priority else "NORMAL"
    )
    db.add(new_source)
    db.flush()

    if topic_id:
        db.add(TopicSource(topic_id=topic_id, source_channel_id=new_source.id))

    db.commit()
    result.added += 1
    result.details.append({"input": feed_url, "status": STATUS_ADDED, "title": title})


def _import_page_line(
    db: Session,
    page_url: str,
    topic_id: Optional[int],
    priority: str,
    result: BulkImportResult
) -> None:
    result.total += 1
    parsed = urlparse(page_url)
    host = (parsed.netloc or "").removeprefix("www.") or "Web"

    existing = db.query(SourceChannel).filter(SourceChannel.url == page_url).first()
    if existing:
        if not existing.is_active:
            restore_if_deleted(db, existing.id)
            result.added += 1
            result.details.append({"input": page_url, "status": STATUS_ADDED, "title": f"{existing.title} (khôi phục)"})
            db.commit()
            return
        result.duplicates += 1
        result.details.append({
            "input": page_url,
            "status": STATUS_DUPLICATE,
            "reason": f"Đã tồn tại trong hệ thống (ID: {existing.id})",
            "title": existing.title
        })
        return

    rem = channels_remaining(db)
    if rem <= 0:
        result.rejected += 1
        result.details.append({"input": page_url, "status": STATUS_REJECTED, "reason": "Đạt giới hạn số kênh của bản quyền"})
        return

    title = f"Trang báo {host}"
    new_source = SourceChannel(
        title=title,
        url=page_url,
        source_type="web",
        is_active=True,
        priority=priority.upper() if priority else "NORMAL"
    )
    db.add(new_source)
    db.flush()

    if topic_id:
        db.add(TopicSource(topic_id=topic_id, source_channel_id=new_source.id))

    db.commit()
    result.added += 1
    result.details.append({"input": page_url, "status": STATUS_ADDED, "title": title})


def bulk_import_channels(
    db: Session,
    raw_lines: List[str],
    topic_id: Optional[int] = None,
    default_priority: str = "NORMAL"
) -> BulkImportResult:
    result = BulkImportResult()
    seen_in_batch = set()

    for line in raw_lines:
        line = line.strip()
        if not line:
            continue

        if line in seen_in_batch:
            result.total += 1
            result.duplicates += 1
            result.details.append({"input": line, "status": STATUS_DUPLICATE, "reason": "Trùng lặp trong danh sách tải lên"})
            continue
        seen_in_batch.add(line)

        # Check if HTTP/HTTPS URL
        if re.match(r"^https?://", line, re.IGNORECASE):
            if re.search(r"(^|//)(www\.)?t\.me/", line, re.IGNORECASE):
                # Telegram link
                url, username, cid = parse_telegram_channel_identifier(line)
                if not url:
                    result.total += 1
                    result.invalid += 1
                    result.details.append({"input": line, "status": STATUS_INVALID, "reason": "Định dạng link Telegram không hợp lệ"})
                    continue
                _import_telegram_source(db, url, username, cid, topic_id, default_priority, result)
            elif looks_like_feed_url(line):
                _import_rss_line(db, line, topic_id, default_priority, result)
            else:
                _import_page_line(db, line, topic_id, default_priority, result)
        else:
            # Telegram handle or username
            url, username, cid = parse_telegram_channel_identifier(line)
            if url:
                _import_telegram_source(db, url, username, cid, topic_id, default_priority, result)
            else:
                result.total += 1
                result.invalid += 1
                result.details.append({"input": line, "status": STATUS_INVALID, "reason": "Định dạng link hoặc username không hợp lệ"})

    return result


def _import_telegram_source(
    db: Session,
    url: str,
    username: Optional[str],
    cid: Optional[str],
    topic_id: Optional[int],
    priority: str,
    result: BulkImportResult
) -> None:
    result.total += 1
    existing = None
    if username:
        existing = db.query(SourceChannel).filter(SourceChannel.username == username).first()
    if not existing:
        existing = db.query(SourceChannel).filter(SourceChannel.url == url).first()

    if existing:
        if not existing.is_active:
            restore_if_deleted(db, existing.id)
            result.added += 1
            result.details.append({"input": url, "status": STATUS_ADDED, "title": f"{existing.title} (khôi phục)"})
            db.commit()
            return
        result.duplicates += 1
        result.details.append({
            "input": url,
            "status": STATUS_DUPLICATE,
            "reason": f"Đã tồn tại trong hệ thống (ID: {existing.id})",
            "title": existing.title
        })
        return

    rem = channels_remaining(db)
    if rem <= 0:
        result.rejected += 1
        result.details.append({"input": url, "status": STATUS_REJECTED, "reason": "Đạt giới hạn số kênh của bản quyền"})
        return

    title = f"Kênh @{username}" if username else f"Kênh Telegram {url}"
    new_source = SourceChannel(
        title=title,
        url=url,
        username=username,
        source_type="telegram",
        is_active=True,
        priority=priority.upper() if priority else "NORMAL"
    )
    db.add(new_source)
    db.flush()

    if topic_id:
        db.add(TopicSource(topic_id=topic_id, source_channel_id=new_source.id))

    db.commit()
    result.added += 1
    result.details.append({"input": url, "status": STATUS_ADDED, "title": title})


def parse_import_file(filename: str, content: bytes) -> List[Dict[str, str]]:
    text = content.decode("utf-8-sig", errors="replace")
    rows: List[Dict[str, str]] = []

    if filename.lower().endswith(".csv"):
        reader = csv.DictReader(io.StringIO(text))
        for r in reader:
            norm = {}
            for k, v in (r or {}).items():
                if not k or not v:
                    continue
                k_clean = k.strip().lower()
                v_clean = v.strip()
                if k_clean in ("url", "link", "username", "kenh", "kênh"):
                    norm["url"] = v_clean
                elif k_clean in ("title", "ten", "tên"):
                    norm["title"] = v_clean
                elif k_clean in ("priority", "uu_tien", "ưu_tiên"):
                    norm["priority"] = v_clean.upper()
                elif k_clean in ("topic", "chu_de", "chủ_đề"):
                    norm["topic"] = v_clean
            if norm.get("url"):
                rows.append(norm)
    else:
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                rows.append({"url": line})

    return rows


def import_rows(
    db: Session,
    rows: List[Dict[str, str]],
    default_topic_id: Optional[int] = None,
    default_priority: str = "NORMAL"
) -> BulkImportResult:
    result = BulkImportResult()
    topics = {t.slug: t.id for t in db.query(Topic).all()}

    for row in rows:
        url = row.get("url")
        if not url:
            continue
        p = row.get("priority", default_priority)
        t_id = default_topic_id
        if row.get("topic") and row["topic"] in topics:
            t_id = topics[row["topic"]]

        batch_res = bulk_import_channels(db, [url], topic_id=t_id, default_priority=p)
        result.total += batch_res.total
        result.added += batch_res.added
        result.duplicates += batch_res.duplicates
        result.invalid += batch_res.invalid
        result.rejected += batch_res.rejected
        result.details.extend(batch_res.details)

    return result
