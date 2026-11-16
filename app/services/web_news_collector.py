import re
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urljoin, urlparse
import httpx
import trafilatura

from app.database import SessionLocal
from app.models import RawPost, RawPostStatus, WorkflowStatus, SourceChannel, MediaItem, MediaType
from app.services.article_fetcher import (
    BROWSER_HEADERS, MAX_HTML_BYTES, MAX_TEXT_CHARS, MIN_TEXT_CHARS,
    extract_article_details
)
from app.services.deduplication import check_deduplication, normalize_post_text, compute_text_hash
from app.services.outbox_dispatcher import queue_post_notifications
from app.services.rss_collector import stable_message_id

logger = logging.getLogger("ak_news.web_news")

VN_TZ = timezone(timedelta(hours=7))
INTERVAL_SECONDS = 300
MAX_NEW_PER_RUN = 10
DELAY_BETWEEN_ARTICLES = 1.0

_NOT_ARTICLE = re.compile(r"/tag/|/tags/|/category/|/chuyen-muc/|/video/|/audio/|/interactive/|/lien-he", re.I)
_PUBLISHED_META = re.compile(
    r'<meta[^>]+(?:property|name|itemprop)=["\'](?:article:published_time|og:published_time|datePublished|pubdate|publishdate)["\'][^>]*content=["\']([^"\']+)["\']|'
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name|itemprop)=["\'](?:article:published_time|datePublished)["\']',
    re.I
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def site_key(host: str) -> str:
    parts = host.lower().split(".")
    if parts and parts[0] == "www":
        parts = parts[1:]
    return parts[0] if parts else host


def looks_like_article(url: str, site: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    if site_key(parsed.hostname or "") != site:
        return False
    path = parsed.path
    if _NOT_ARTICLE.search(path):
        return False
    segments = [s for s in path.split("/") if s]
    if not segments:
        return False
    last = segments[-1]
    if re.search(r"\d{5,}", last) or last.endswith(".html") or last.endswith(".htm"):
        return True
    return len(segments) >= 2


def article_links(html_text: str, page_url: str, site: str) -> List[str]:
    raw_hrefs = re.findall(r'href=["\']([^"\']+)["\']', html_text, re.I)
    links = []
    seen = set()
    for h in raw_hrefs:
        full = urljoin(page_url, h.split("#")[0]).strip()
        if full not in seen and looks_like_article(full, site):
            seen.add(full)
            links.append(full)
    return links


def parse_article(html_text: str, url: str) -> Dict[str, Any]:
    return extract_article_details(html_text, url=url)


async def collect_source(client: httpx.AsyncClient, db: Any, src: SourceChannel) -> Tuple[int, int]:
    page_url = src.url or src.rss_url or ""
    if not page_url:
        return 0, 0
    site = site_key(urlparse(page_url).hostname or "")
    try:
        resp = await client.get(page_url, headers=BROWSER_HEADERS, timeout=30.0, follow_redirects=True)
        if resp.status_code != 200:
            return 0, 0
        links = article_links(resp.text, str(resp.url), site)
    except Exception as e:
        logger.warning(f"Web source #{src.id} fetch error: {e}")
        return 0, 0

    known = set(r[0] for r in db.query(RawPost.source_url).filter(RawPost.source_url.in_(links)).all())
    fresh = [l for l in links if l not in known][:MAX_NEW_PER_RUN]

    new_count = 0
    dup_count = 0
    for link in fresh:
        await asyncio.sleep(DELAY_BETWEEN_ARTICLES)
        try:
            art_resp = await client.get(link, headers=BROWSER_HEADERS, timeout=20.0, follow_redirects=True)
            if art_resp.status_code != 200:
                continue
            art = parse_article(art_resp.text, str(art_resp.url))
            text = (art.get("text") or "").strip()
            if len(text) < MIN_TEXT_CHARS:
                continue

            title = art.get("title") or ""
            content = f"{title}\n\n{text}"
            norm = normalize_post_text(content)
            is_dup, _ = check_deduplication(norm)
            if is_dup:
                dup_count += 1
                continue

            thash = compute_text_hash(norm)
            mid = stable_message_id(link)
            post = RawPost(
                source_channel_id=src.id,
                channel_message_id=mid,
                source_url=link,
                title=title,
                original_text=content,
                text_hash=thash,
                status=RawPostStatus.NEW.value,
                workflow_status=WorkflowStatus.CLAIMED.value,
                article_text=text,
                article_status="ok",
                article_fetched_at=_utcnow()
            )
            db.add(post)
            db.flush()

            if art.get("image"):
                db.add(MediaItem(
                    raw_post_id=post.id,
                    media_type=MediaType.PHOTO.value,
                    file_path=art["image"],
                    file_size_bytes=0
                ))
            db.commit()
            queue_post_notifications(post, title, [src.id])
            new_count += 1
        except Exception as e:
            logger.info(f"Skip article {link}: {e}")
            continue

    src.last_fetched_at = _utcnow()
    db.commit()
    return new_count, dup_count


async def sync_web_sources_async(source_id: Optional[int] = None) -> Dict[str, int]:
    db = SessionLocal()
    try:
        q = db.query(SourceChannel).filter(SourceChannel.source_type == "web", SourceChannel.is_active == True)
        if source_id:
            q = q.filter(SourceChannel.id == source_id)
        sources = q.all()
        if not sources:
            return {"new": 0, "duplicate": 0}

        total_new = 0
        total_dup = 0
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for s in sources:
                n, d = await collect_source(client, db, s)
                total_new += n
                total_dup += d

        return {"new": total_new, "duplicate": total_dup}
    finally:
        db.close()


def sync_web_sources(source_id: Optional[int] = None) -> Dict[str, int]:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(sync_web_sources_async(source_id))).result()
    else:
        return asyncio.run(sync_web_sources_async(source_id))


async def web_news_worker_loop():
    logger.info("Newspaper page collector (sites without RSS) started.")
    while True:
        try:
            res = await sync_web_sources_async()
            logger.info(f"Web news sync: +{res['new']} new, {res['duplicate']} duplicates")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Web news worker error: {e}")
        await asyncio.sleep(INTERVAL_SECONDS)
