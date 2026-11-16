"""Standalone CLI for logging in Telegram via Telethon user session."""

import asyncio
from telethon import TelegramClient
from app.config import settings


async def main():
    if not settings.TELEGRAM_API_ID or not settings.TELEGRAM_API_HASH:
        print("Thiếu TELEGRAM_API_ID / TELEGRAM_API_HASH trong file .env (lấy tại https://my.telegram.org).")
        return
    session_path = str(settings.data_dir / settings.TELEGRAM_SESSION_NAME)
    phone = settings.TELEGRAM_PHONE or input("Số điện thoại (+84...): ")
    client = TelegramClient(session_path, settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)
    await client.start(phone=lambda: phone)
    me = await client.get_me()
    print(f"Đã đăng nhập: {me.first_name} (@{me.username}). Phiên lưu tại {session_path}.session")
    print("Khởi động lại iNew để bắt đầu thu thập.")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
