import re
import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, List, Dict, Any

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import RawPost, SourceChannel, AppSetting
from app.services.media_fetcher import is_public_http_url

logger = logging.getLogger("ak_news.article_fetcher")

MIN_TEXT_CHARS = 100
MAX_TEXT_CHARS = 50000
MAX_HTML_BYTES = 5 * 1024 * 1024  # 5 MB
LOOKBACK_DAYS = 7
RETRY_MARK_KEY = "article_fetcher_last_retry"
CONCURRENCY = 3
BATCH = 10

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Regex to detect boilerplate/noise lines in Vietnamese news
NOISE_LINE_PATTERNS = [
    re.compile(r"^(?:>>>\s*)?(?:xem|đọc|tham\s+khảo)\s+thêm\b.*", re.IGNORECASE),
    re.compile(r"^(?:bài\s+viết\s+liên\s+quan|tin\s+liên\s+quan|chủ\s+đề\s+liên\s+quan|có\s+thể\s+bạn\s+quan\s+tâm)\b.*", re.IGNORECASE),
    re.compile(r"^(?:nguồn|theo|ảnh|video|đồ\s+họa|thực\s+hiện|biên\s+tập|bài\s+và\s+ảnh)\s*:\s*.*", re.IGNORECASE),
    re.compile(r"^(?:từ\s+khóa|tag|tags)\s*:\s*.*", re.IGNORECASE),
    re.compile(r".*bản\s+quyền\s+thuộc\s+về.*", re.IGNORECASE),
    re.compile(r".*(?:mọi\s+hành\s+vi\s+sao\s+chép|cấm\s+sao\s+chép|vui\s+lòng\s+ghi\s+rõ\s+nguồn).*", re.IGNORECASE),
    re.compile(r".*(?:hotline|đường\s+dây\s+nóng|hòm\s+thư|toà\s+soạn|tòa\s+soạn)\s*:\s*.*", re.IGNORECASE),
    re.compile(r".*(?:theo\s+dõi\s+chúng\s+tôi\s+trên|kết\s+nối\s+với\s+chúng\s+tôi|nhấn\s+vào\s+đây\s+để).*", re.IGNORECASE),
]


def clean_article_noise(text: str) -> str:
    """Filter out boilerplate, advertisement and noise lines from extracted text."""
    if not text:
        return ""
    cleaned_lines = []
    for line in text.splitlines():
        line_s = line.strip()
        if not line_s:
            continue
        is_noise = False
        for pat in NOISE_LINE_PATTERNS:
            if pat.search(line_s):
                is_noise = True
                break
        if not is_noise:
            cleaned_lines.append(line_s)
    return "\n\n".join(cleaned_lines)


def _extractor_ok() -> bool:
    try:
        import trafilatura
        return True
    except ImportError:
        return False


def extract_article_details(html: str, url: str = "") -> Dict[str, Any]:
    if not html:
        return {"text": "", "title": "", "lead": "", "author": "", "published": "", "image": ""}

    # 1. Primary: Trafilatura with JSON and Metadata
    try:
        import trafilatura
        raw_json = trafilatura.extract(
            html,
            url=url,
            output_format="json",
            with_metadata=True,
            include_comments=False,
            include_tables=True,
            favor_precision=True
        )
        data = json.loads(raw_json) if raw_json else None
        extracted_text = data.get("text") if data else ""
        
        # If precision mode gave insufficient text, retry with favor_recall
        if not extracted_text or len(extracted_text.strip()) < MIN_TEXT_CHARS:
            raw_json_recall = trafilatura.extract(
                html,
                url=url,
                output_format="json",
                with_metadata=True,
                include_comments=False,
                include_tables=True,
                favor_recall=True
            )
            if raw_json_recall:
                data = json.loads(raw_json_recall)

        if data and data.get("text"):
            cleaned = clean_article_noise(data.get("text") or "")
            if len(cleaned) >= MIN_TEXT_CHARS:
                return {
                    "text": cleaned[:MAX_TEXT_CHARS],
                    "title": (data.get("title") or "").strip(),
                    "lead": (data.get("excerpt") or data.get("description") or "").strip(),
                    "author": (data.get("author") or "").strip(),
                    "published": (data.get("date") or "").strip(),
                    "image": (data.get("image") or "").strip()
                }
    except Exception as e:
        logger.debug(f"Trafilatura extraction failed for {url}: {e}")

    # 2. Fallback: BeautifulSoup heuristic extraction with VN media selectors
    try:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "iframe", "noscript", "svg"]):
            tag.decompose()

        for tag in soup.find_all(attrs={"class": re.compile(r"\b(?:advert|banner|social-share|related-post|sidebar|box-comment)\b", re.I)}):
            tag.decompose()

        title = ""
        og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        elif soup.find("title"):
            title = soup.find("title").get_text().strip()

        image = ""
        og_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
        if og_img and og_img.get("content"):
            image = og_img["content"].strip()

        lead = ""
        og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
        if og_desc and og_desc.get("content"):
            lead = og_desc["content"].strip()

        selectors = [
            "article.fck_detail",
            "div.singular-content",
            "div.content-fck",
            "div.detail-content",
            "div.maincontent",
            "div.the-article-body",
            "div.contentdetail",
            "article",
            "[itemprop='articleBody']",
            "div[class*='post-body']",
            "div[class*='article-content']",
            "div[class*='entry-content']",
            "div[class*='content-detail']"
        ]

        body = None
        for sel in selectors:
            found = soup.select_one(sel)
            if found:
                body = found
                break
        if not body:
            body = soup.find("article") or soup.find("main") or soup.body or soup

        paragraphs = [p.get_text().strip() for p in body.find_all("p")]
        meaningful = [p for p in paragraphs if len(p) > 25]
        raw_text = "\n\n".join(meaningful)
        cleaned = clean_article_noise(raw_text)

        if len(cleaned) >= MIN_TEXT_CHARS:
            return {
                "text": cleaned[:MAX_TEXT_CHARS],
                "title": title,
                "lead": lead,
                "author": "",
                "published": "",
                "image": image
            }
    except Exception as e:
        logger.debug(f"BeautifulSoup fallback failed for {url}: {e}")

    return {"text": "", "title": "", "lead": "", "author": "", "published": "", "image": ""}


def extract_main_text(html: str, url: str = "") -> str:
    details = extract_article_details(html, url=url)
    return details.get("text") or ""


async def fetch_article_details(
    url: str,
    client: Optional[httpx.AsyncClient] = None
) -> Tuple[bool, Dict[str, Any], str]:
    if not is_public_http_url(url):
        return False, {}, "Link không hợp lệ hoặc địa chỉ nội bộ."

    owns_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=BROWSER_HEADERS)
        owns_client = True

    try:
        async with client.stream("GET", url) as resp:
            if resp.status_code != 200:
                return False, {}, f"Trang báo trả về lỗi HTTP {resp.status_code}"

            chunks = []
            total = 0
            async for chunk in resp.aiter_bytes(chunk_size=16384):
                chunks.append(chunk)
                total += len(chunk)
                if total > MAX_HTML_BYTES:
                    return False, {}, "Trang quá lớn (> 5MB)"

            encoding = resp.encoding or "utf-8"
            html = b"".join(chunks).decode(encoding, errors="replace")

        details = extract_article_details(html, url=url)
        text = details.get("text") or ""
        if not text or len(text) < MIN_TEXT_CHARS:
            return False, details, "Không trích được nội dung bài (trang video, chặn truy cập hoặc cần đăng nhập)"

        return True, details, ""
    except httpx.TimeoutException:
        return False, {}, "Trang báo phản hồi quá lâu (Timeout)"
    except Exception as e:
        return False, {}, f"Không tải được trang: {e}"
    finally:
        if owns_client:
            await client.aclose()


async def fetch_article_text(
    url: str,
    client: Optional[httpx.AsyncClient] = None
) -> Tuple[bool, str, str]:
    ok, details, reason = await fetch_article_details(url, client=client)
    return ok, details.get("text", "") if ok else "", reason


async def fetch_for_post(post_id: int, client: Optional[httpx.AsyncClient] = None) -> bool:
    db: Session = SessionLocal()
    try:
        post = db.query(RawPost).filter(RawPost.id == post_id).first()
        if not post or not post.source_url:
            return False

        ok, details, reason = await fetch_article_details(post.source_url, client=client)
        post.article_fetched_at = datetime.now(timezone.utc)
        if ok and details.get("text"):
            text = details["text"]
            post.article_status = "ok"
            post.article_text = text
            if (not post.title or len(post.title.strip()) < 5) and details.get("title"):
                post.title = details["title"]
            if details.get("image") and not post.has_media:
                post.has_media = True
            logger.info(f"Đã lấy toàn văn ({len(text)} ký tự) cho post #{post.id}")
        else:
            post.article_status = "failed"
            logger.debug(f"Lỗi trích nội dung post #{post.id}: {reason}")

        db.commit()
        return ok
    finally:
        db.close()


def _pending_ids(db: Session, limit: int = BATCH) -> List[int]:
    rows = (
        db.query(RawPost.id)
        .join(SourceChannel, RawPost.source_id == SourceChannel.id)
        .filter(
            SourceChannel.source_type.in_(["rss", "web"]),
            RawPost.article_status.is_(None),
            RawPost.source_url.isnot(None)
        )
        .order_by(RawPost.created_at.desc())
        .limit(limit)
        .all()
    )
    return [r[0] for r in rows]


async def article_worker_loop(interval_seconds: int = 45):
    if not settings.ARTICLE_FULLTEXT_ENABLED:
        logger.info("Full-text article fetching is disabled (ARTICLE_FULLTEXT_ENABLED=false).")
        return

    logger.info("Full-text article worker started.")
    sem = asyncio.Semaphore(CONCURRENCY)

    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers=BROWSER_HEADERS) as client:
        while True:
            try:
                db: Session = SessionLocal()
                try:
                    pids = _pending_ids(db, limit=BATCH)
                finally:
                    db.close()

                if pids:
                    async def _fetch_one(pid):
                        async with sem:
                            await fetch_for_post(pid, client=client)

                    await asyncio.gather(*[_fetch_one(pid) for pid in pids], return_exceptions=True)
            except Exception as e:
                logger.error(f"Article worker error: {e}")

            await asyncio.sleep(interval_seconds)


fetch_article_for_post = fetch_for_post
