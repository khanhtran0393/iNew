import base64
import hashlib
from cryptography.fernet import Fernet
from app.config import settings


def _get_fernet_key() -> bytes:
    key_material = (settings.SECRET_KEY or settings.DEFAULT_SECRET_KEY).encode("utf-8")
    digest = hashlib.sha256(key_material).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(plain_text: str) -> str:
    if not plain_text:
        return ""
    f = Fernet(_get_fernet_key())
    return f.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher_text: str) -> str:
    if not cipher_text:
        return ""
    try:
        f = Fernet(_get_fernet_key())
        return f.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except Exception:
        return cipher_text
