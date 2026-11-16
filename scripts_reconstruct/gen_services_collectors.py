import os
from pathlib import Path

services_dir = Path("app/services")

# 1. rss_collector.py
(services_dir / "rss_collector.py").write_text('''import re
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
    clean = re.sub(r"\\s+", " ", clean)
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
            text_content = f"{title}\\n\\n{desc}".strip()
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
''', encoding="utf-8")

# 2. article_fetcher.py
(services_dir / "article_fetcher.py").write_text('''import logging
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("inew.article")


def extract_main_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    paragraphs = [p.get_text().strip() for p in soup.find_all("p")]
    return "\\n\\n".join([p for p in paragraphs if len(p) > 40])


def fetch_article_text(url: str) -> str:
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            if resp.status_code == 200:
                return extract_main_text(resp.text)
    except Exception as e:
        logger.warning(f"Failed to fetch article {url}: {e}")
    return ""
''', encoding="utf-8")

# 3. web_news_collector.py
(services_dir / "web_news_collector.py").write_text('''import logging
logger = logging.getLogger("inew.web_news")

def sync_web_sources() -> int:
    return 0
''', encoding="utf-8")

# 4. telegram_web_collector.py
(services_dir / "telegram_web_collector.py").write_text('''import logging
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("inew.tg_web")

def parse_preview_page(html: str):
    soup = BeautifulSoup(html, "html.parser")
    messages = []
    for msg in soup.find_all("div", class_="tgme_widget_message"):
        text_el = msg.find("div", class_="tgme_widget_message_text")
        text = text_el.get_text().strip() if text_el else ""
        if text:
            messages.append(text)
    return messages
''', encoding="utf-8")

# 5. telegram_bot.py
(services_dir / "telegram_bot.py").write_text('''import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from app.config import settings
from app.database import SessionLocal
from app.models import OutboxNotification, User

logger = logging.getLogger("inew.bot")


def setup_bot_handlers(dp: Dispatcher):
    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        await message.answer(
            f"Chào bạn đến với iNew Editorial Bot!\\n"
            f"Hệ thống tin tức và quản trị xuất bản tự động.\\n"
            f"Telegram ID của bạn là: <code>{message.from_user.id}</code>",
            parse_mode="HTML"
        )


async def dispatch_pending_outbox():
    if not settings.TELEGRAM_BOT_TOKEN:
        return
    db = SessionLocal()
    try:
        pending = (
            db.query(OutboxNotification)
            .filter_by(status="pending")
            .limit(10)
            .all()
        )
        if not pending:
            return

        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        for item in pending:
            try:
                await bot.send_message(chat_id=item.target_chat_id, text=item.text)
                item.status = "sent"
            except Exception as e:
                logger.error(f"Failed to send outbox notification {item.id}: {e}")
                item.retry_count += 1
                if item.retry_count > 3:
                    item.status = "failed"
        db.commit()
    finally:
        db.close()
''', encoding="utf-8")

# 6. telegram_ingestion.py
(services_dir / "telegram_ingestion.py").write_text('''import asyncio
import logging
from telethon import TelegramClient, events
from app.config import settings

logger = logging.getLogger("inew.telethon")
_client = None

def get_client():
    global _client
    if not _client and settings.TELEGRAM_API_ID and settings.TELEGRAM_API_HASH:
        _client = TelegramClient(
            settings.TELEGRAM_SESSION_NAME,
            int(settings.TELEGRAM_API_ID),
            settings.TELEGRAM_API_HASH
        )
    return _client
''', encoding="utf-8")

# 7. outbox_dispatcher.py
(services_dir / "outbox_dispatcher.py").write_text('''from app.database import SessionLocal
from app.models import OutboxNotification

def queue_post_notifications(post, text: str, target_chat_ids: list):
    db = SessionLocal()
    try:
        for cid in target_chat_ids:
            notif = OutboxNotification(
                target_chat_id=cid,
                raw_post_id=post.id,
                text=text,
                status="pending"
            )
            db.add(notif)
        db.commit()
    finally:
        db.close()
''', encoding="utf-8")

print("Generated collector services (rss, article, web news, tg web, tg bot, tg ingestion, outbox)")
