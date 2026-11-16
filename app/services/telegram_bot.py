import logging
from typing import Optional
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from app.config import settings
from app.database import SessionLocal
from app.models import OutboxNotification, User

logger = logging.getLogger("ak_news.telegram_bot")


def setup_bot_handlers(dp: Dispatcher):
    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        await message.answer(
            f"Chào bạn đến với iNew Editorial Bot!\n"
            f"Hệ thống tin tức và quản trị xuất bản tự động.\n"
            f"Telegram ID của bạn là: <code>{message.from_user.id}</code>",
            parse_mode="HTML"
        )


async def send_telegram_message(
    chat_id: int,
    text: str,
    parse_mode: Optional[str] = "HTML"
) -> bool:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.debug("TELEGRAM_BOT_TOKEN not configured; skipping dispatch.")
        return False
    try:
        bot = Bot(token=token)
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        except Exception as pe:
            if parse_mode:
                # Fallback to plain text if HTML parsing failed
                await bot.send_message(chat_id=chat_id, text=text, parse_mode=None)
            else:
                raise pe
        await bot.session.close()
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
        return False


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

        for item in pending:
            ok = await send_telegram_message(chat_id=item.target_chat_id, text=item.text)
            if ok:
                item.status = "sent"
            else:
                item.retry_count = (item.retry_count or 0) + 1
                if item.retry_count > 3:
                    item.status = "failed"
        db.commit()
    finally:
        db.close()
