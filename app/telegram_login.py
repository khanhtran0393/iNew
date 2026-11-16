import asyncio
from typing import Dict, Any, Optional
from telethon import TelegramClient
from app.config import settings

_login_client: Optional[TelegramClient] = None
_phone_code_hash: Optional[str] = None
_phone_number: Optional[str] = None


async def send_code_request(phone: str, api_id: int, api_hash: str) -> Dict[str, Any]:
    global _login_client, _phone_code_hash, _phone_number
    _phone_number = phone.strip()
    _login_client = TelegramClient(settings.TELEGRAM_SESSION_NAME, api_id, api_hash)
    await _login_client.connect()
    res = await _login_client.send_code_request(_phone_number)
    _phone_code_hash = res.phone_code_hash
    return {"ok": True, "phone_code_hash": _phone_code_hash}


async def verify_login_code(code: str, password: Optional[str] = None) -> Dict[str, Any]:
    global _login_client, _phone_code_hash, _phone_number
    if not _login_client or not _phone_code_hash:
        return {"ok": False, "error": "Chưa gửi mã xác nhận"}
    try:
        await _login_client.sign_in(_phone_number, code, phone_code_hash=_phone_code_hash)
    except Exception as e:
        if "Two-steps verification is enabled" in str(e) and password:
            await _login_client.sign_in(password=password)
        else:
            return {"ok": False, "error": str(e)}

    session_string = _login_client.session.save()
    await _login_client.disconnect()
    _login_client = None
    return {"ok": True, "session_string": session_string}
