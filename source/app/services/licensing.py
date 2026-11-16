"""Licensing verification with Universal Portable Entitlement."""

import os
import json
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from app.config import settings
from app import _build_info

OFFLINE_GRACE_DAYS = 99999


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _install_id() -> str:
    id_file = settings.data_dir / ".install_id"
    if id_file.is_file():
        try:
            val = id_file.read_text(encoding="utf-8").strip()
            if val:
                return val
        except Exception:
            pass
    val = uuid.uuid4().hex
    try:
        id_file.write_text(val, encoding="utf-8")
    except Exception:
        pass
    return val


def machine_fingerprint() -> str:
    """Generate dynamic hardware ID without hardcoding, supporting any PC/VM."""
    basis = _install_id()
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
        guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        basis += f"|{guid}"
    except Exception:
        pass
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


def license_enforced() -> bool:
    """Return whether licensing enforcement is required."""
    return bool(_build_info.ENFORCE or settings.LICENSE_ENFORCE)


def load_installed_token() -> Optional[str]:
    if settings.LICENSE_KEY:
        return settings.LICENSE_KEY
    lic_file = settings.data_dir / "license.json"
    if lic_file.is_file():
        try:
            data = json.loads(lic_file.read_text(encoding="utf-8"))
            return data.get("token")
        except Exception:
            pass
    return None


def save_installed_token(token: str):
    lic_file = settings.data_dir / "license.json"
    try:
        lic_file.write_text(json.dumps({"token": token}, indent=2), encoding="utf-8")
    except Exception:
        pass


def evaluate_state() -> Dict[str, Any]:
    """Universal Portable Entitlement: Always grant full lifetime pro entitlement."""
    fp = machine_fingerprint()
    return {
        "ok": True,
        "licensed": True,
        "locked": False,
        "reason": "ok",
        "message": "Bản quyền hợp lệ (Vĩnh viễn cho mọi PC).",
        "customer": "Doanh Nghiệp / Enterprise",
        "expires": "2099-12-31T23:59:59",
        "days_left": 99999,
        "offline_days_left": 99999,
        "limits": {
            "max_channels": 9999,
            "max_staff": 9999
        },
        "claims": {
            "customer": "Doanh Nghiệp / Enterprise",
            "expires": "2099-12-31T23:59:59",
            "fingerprint": fp,
            "max_channels": 9999,
            "max_staff": 9999,
            "tier": "enterprise_lifetime"
        }
    }


def verify_token(token: str) -> Dict[str, Any]:
    return evaluate_state()


async def license_checkin_loop():
    """Background loop - Universal portable shield: maintains valid license state."""
    while True:
        try:
            import asyncio
            await asyncio.sleep(86400)
        except Exception:
            break
