import os
from pathlib import Path

services_dir = Path("app/services")
services_dir.mkdir(parents=True, exist_ok=True)

(services_dir / "__init__.py").write_text('"""iNew Core Services Package."""\n', encoding="utf-8")

# 1. security_crypto.py
(services_dir / "security_crypto.py").write_text('''import base64
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
''', encoding="utf-8")

# 2. runtime_config.py
(services_dir / "runtime_config.py").write_text('''from app.database import SessionLocal
from app.models import AppSetting


def _get(key: str, default: str = "") -> str:
    db = SessionLocal()
    try:
        s = db.query(AppSetting).filter_by(key=key).first()
        return s.value if s else default
    finally:
        db.close()


def _set(key: str, value: str) -> None:
    db = SessionLocal()
    try:
        s = db.query(AppSetting).filter_by(key=key).first()
        if s:
            s.value = value
        else:
            db.add(AppSetting(key=key, value=value))
        db.commit()
    finally:
        db.close()


def setup_completed() -> bool:
    return _get("setup_completed", "false").lower() == "true"


def mark_setup_completed() -> None:
    _set("setup_completed", "true")


def ensure_setup_flag() -> None:
    if not setup_completed():
        pass


def save_config(key: str, value: str) -> None:
    _set(key, value)


def apply_saved_config() -> None:
    pass
''', encoding="utf-8")

# 3. licensing.py
(services_dir / "licensing.py").write_text('''import os
import json
import base64
import uuid
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
import httpx
from app.config import settings
from app import _build_info

logger = logging.getLogger("inew.licensing")
OFFLINE_GRACE_DAYS = 15


def _b64url_decode(s: str) -> bytes:
    pad = len(s) % 4
    if pad:
        s += "=" * (4 - pad)
    return base64.urlsafe_b64decode(s)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _in_container() -> bool:
    return Path("/.dockerenv").is_file() or Path("/run/.containerenv").is_file()


def _install_id() -> str:
    file = settings.data_dir / ".install_id"
    if file.is_file():
        val = file.read_text(encoding="utf-8").strip()
        if val:
            return val
    new_id = uuid.uuid4().hex
    file.write_text(new_id, encoding="utf-8")
    return new_id


def _hardware_id() -> str:
    if os.name == "nt":
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\Microsoft\\Cryptography")
            guid, _ = winreg.QueryValueEx(k, "MachineGuid")
            winreg.CloseKey(k)
            return guid
        except Exception:
            pass
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        p = Path(path)
        if p.is_file():
            return p.read_text().strip()
    return f"{uuid.getnode():012x}"


def machine_fingerprint() -> str:
    install = _install_id()
    hw = _hardware_id()
    if _in_container():
        basis = f"docker|{install}|{hw}"
    else:
        basis = f"{install}|{hw}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def license_enforced() -> bool:
    return getattr(_build_info, "ENFORCE", True) and settings.LICENSE_ENFORCE


def license_server_url() -> str:
    return getattr(_build_info, "LICENSE_SERVER_URL", "") or settings.LICENSE_SERVER_URL


def _vendor_public_key() -> Optional[Ed25519PublicKey]:
    raw = (
        getattr(_build_info, "PUBLIC_KEY", "")
        or settings.LICENSE_PUBLIC_KEY
        or os.environ.get("LICENSE_PUBLIC_KEY", "")
    )
    if not raw:
        return None
    try:
        pub_bytes = _b64url_decode(raw.strip())
        return Ed25519PublicKey.from_public_bytes(pub_bytes)
    except Exception as e:
        logger.error(f"Bad license public key: {e}")
        return None


def verify_token(token: str) -> Tuple[bool, Dict[str, Any], str]:
    pub = _vendor_public_key()
    if not pub:
        return False, {}, "Phần mềm chưa gắn khóa bản quyền của tác giả."
    if "." not in token:
        return False, {}, "Mã bản quyền sai định dạng."
    try:
        payload_b64, sig_b64 = token.strip().split(".", 1)
        payload = _b64url_decode(payload_b64)
        signature = _b64url_decode(sig_b64)
        pub.verify(signature, payload)
        claims = json.loads(payload.decode("utf-8"))
        return True, claims, ""
    except InvalidSignature:
        return False, {}, "Chữ ký bản quyền không hợp lệ (mã giả hoặc đã bị sửa)."
    except Exception as e:
        return False, {}, f"Mã bản quyền không đọc được: {e}"


def _license_file() -> Path:
    return settings.data_dir / "license.json"


def _state_file() -> Path:
    return settings.data_dir / "license_state.json"


def load_installed_token() -> str:
    env_token = os.environ.get("LICENSE_KEY")
    if env_token:
        return env_token.strip()
    f = _license_file()
    if f.is_file():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            return data.get("token", "").strip()
        except Exception:
            pass
    return ""


def save_installed_token(token: str) -> None:
    data = {"token": token.strip(), "installed_at": _utcnow().isoformat()}
    _license_file().write_text(json.dumps(data, indent=2), encoding="utf-8")


def _read_state() -> Dict[str, Any]:
    f = _state_file()
    if f.is_file():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _write_state(data: Dict[str, Any]) -> None:
    _state_file().write_text(json.dumps(data, indent=2), encoding="utf-8")


def evaluate_state() -> Dict[str, Any]:
    token = load_installed_token()
    if not token:
        return {
            "licensed": False,
            "locked": True,
            "reason": "no_license",
            "message": "Máy này chưa được kích hoạt.",
            "claims": {},
            "customer": "",
            "expires": None,
            "limits": {"max_channels": None, "max_staff": None},
            "offline_days_left": None
        }

    ok, claims, err = verify_token(token)
    if not ok:
        return {
            "licensed": False,
            "locked": True,
            "reason": "invalid",
            "message": err,
            "claims": {}
        }

    # Verify bound fingerprint
    bound_fp = claims.get("fingerprint")
    current_fp = machine_fingerprint()
    if bound_fp and bound_fp != current_fp:
        return {
            "licensed": False,
            "locked": True,
            "reason": "wrong_machine",
            "message": "Mã bản quyền này đã kích hoạt cho một máy khác.",
            "claims": claims
        }

    # Check expiry
    expiry = claims.get("expires")
    if expiry:
        exp_dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        if exp_dt < _utcnow():
            return {
                "licensed": False,
                "locked": True,
                "reason": "expired",
                "message": f"Bản quyền đã hết hạn ngày {exp_dt.strftime('%d/%m/%Y')}.",
                "claims": claims
            }

    state = _read_state()
    if state.get("revoked"):
        return {
            "licensed": False,
            "locked": True,
            "reason": "revoked",
            "message": "Key kích hoạt đã bị tác giả thu hồi.",
            "claims": claims
        }

    return {
        "licensed": True,
        "locked": False,
        "reason": "ok",
        "message": "Bản quyền hợp lệ.",
        "customer": claims.get("customer", "Người dùng iNew"),
        "expires": expiry,
        "limits": {
            "max_channels": claims.get("max_channels"),
            "max_staff": claims.get("max_staff")
        },
        "offline_days_left": OFFLINE_GRACE_DAYS
    }


def current_limits() -> Dict[str, Any]:
    st = evaluate_state()
    return st.get("limits", {"max_channels": None, "max_staff": None})


async def activate_online(activation_code: str) -> Dict[str, Any]:
    url = license_server_url()
    if not url:
        return {"ok": False, "error": "Chưa cấu hình máy chủ kích hoạt."}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{url.rstrip('/')}/api/activate",
                json={"code": activation_code, "fingerprint": machine_fingerprint()}
            )
            if resp.status_code == 200:
                token = resp.json().get("token")
                if token:
                    save_installed_token(token)
                    return {"ok": True, "token": token}
            return {"ok": False, "error": f"Lỗi kích hoạt ({resp.status_code}): {resp.text}"}
    except Exception as e:
        return {"ok": False, "error": f"Không thể kết nối máy chủ: {e}"}
''', encoding="utf-8")

# 4. tasks.py
(services_dir / "tasks.py").write_text('''import asyncio
from typing import Coroutine

def spawn(coro: Coroutine) -> asyncio.Task:
    """Safely spawn a fire-and-forget background asyncio task."""
    return asyncio.create_task(coro)
''', encoding="utf-8")

# 5. staff_notify.py
(services_dir / "staff_notify.py").write_text('''import uuid
from datetime import datetime, timezone
from typing import Optional
from app.database import SessionLocal
from app.models import OutboxNotification, User


def create_link_token(user_id: int) -> str:
    return uuid.uuid4().hex[:12]


def consume_link_token(token: str) -> Optional[int]:
    return None


async def notify_user(user: User, text: str) -> None:
    if not user.telegram_id:
        return
    db = SessionLocal()
    try:
        notif = OutboxNotification(
            target_chat_id=user.telegram_id,
            text=text,
            status="pending"
        )
        db.add(notif)
        db.commit()
    finally:
        db.close()


def notify_in_background(user: User, text: str) -> None:
    pass
''', encoding="utf-8")

# 6. deduplication.py
(services_dir / "deduplication.py").write_text('''import re
import hashlib
from typing import Tuple, Optional
from rapidfuzz import fuzz
from app.database import SessionLocal
from app.models import RawPost
from app.config import settings


def normalize_post_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"https?://\\S+", "", text)
    text = re.sub(r"[#@][\\w_]+", "", text)
    text = re.sub(r"\\s+", " ", text)
    return text.strip().lower()


def compute_text_hash(text: str) -> str:
    norm = normalize_post_text(text)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def check_deduplication(text: str, current_post_id: Optional[int] = None) -> Tuple[bool, Optional[int]]:
    if not text:
        return False, None
    h = compute_text_hash(text)
    db = SessionLocal()
    try:
        exact = db.query(RawPost).filter(RawPost.text_hash == h).first()
        if exact and exact.id != current_post_id:
            return True, exact.id

        norm = normalize_post_text(text)
        if len(norm) > 50 and settings.ENABLE_SEMANTIC_DEDUP:
            recent_posts = (
                db.query(RawPost.id, RawPost.original_text)
                .order_by(RawPost.created_at.desc())
                .limit(200)
                .all()
            )
            for pid, rtext in recent_posts:
                if pid == current_post_id or not rtext:
                    continue
                rnorm = normalize_post_text(rtext)
                ratio = fuzz.ratio(norm, rnorm)
                if ratio >= settings.DEDUP_FUZZY_THRESHOLD:
                    return True, pid
        return False, None
    finally:
        db.close()
''', encoding="utf-8")

# 7. media_storage.py
(services_dir / "media_storage.py").write_text('''import os
import shutil
import hashlib
from pathlib import Path
from typing import Optional
from app.config import settings


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def prepare_media_target_path(post_id: int, filename: str) -> Path:
    folder = settings.raw_media_dir / str(post_id)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / filename


def is_disk_full_or_critical() -> bool:
    usage = shutil.disk_usage(settings.data_dir)
    pct = (usage.used / usage.total) * 100
    return pct >= settings.DISK_WATCHDOG_THRESHOLD_PERCENT


def get_disk_usage() -> dict:
    usage = shutil.disk_usage(settings.data_dir)
    return {
        "total_gb": round(usage.total / (1024**3), 2),
        "used_gb": round(usage.used / (1024**3), 2),
        "free_gb": round(usage.free / (1024**3), 2),
        "used_percent": round((usage.used / usage.total) * 100, 1)
    }
''', encoding="utf-8")

# 8. media_fetcher.py
(services_dir / "media_fetcher.py").write_text('''import asyncio
from pathlib import Path
from typing import Optional
import httpx
from app.config import settings


async def download_image_to_disk(url: str, target_path: Path) -> bool:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(resp.content)
                return True
        return False
    except Exception:
        return False
''', encoding="utf-8")

# 9. desktop.py
(services_dir / "desktop.py").write_text('''from app.config import settings

def currently_lan() -> bool:
    return settings.ALLOW_LAN

def set_allow_lan(enabled: bool) -> None:
    settings.ALLOW_LAN = enabled

def request_restart() -> None:
    pass
''', encoding="utf-8")

print("Generated core services (crypto, config, licensing, deduplication, media, desktop)")
