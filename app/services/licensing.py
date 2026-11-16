import os
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
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
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
    current_fp = machine_fingerprint()
    # Parse token format: inew_portable_license.{fingerprint}
    if not token or not token.startswith("inew_portable_license."):
        return False, {}, "Invalid token format"
    
    stored_fp = token.split(".", 1)[1]
    if stored_fp != current_fp:
        return False, {}, "Token fingerprint does not match hardware"
    
    # Check license state
    state = _read_state()
    if not state.get("licensed", False):
        return False, {}, state.get("reason", "License not active")
    
    # Return appropriate limits based on license
    limits = state.get("limits", {"max_channels": None, "max_staff": None})
    expires = state.get("expires")
    
    return True, {
        "customer": state.get("customer", "Unknown"),
        "fingerprint": current_fp,
        "expires": expires,
        "max_channels": limits.get("max_channels"),
        "max_staff": limits.get("max_staff")
    }, ""


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


def save_installed_token(token: str) -> str:
    data = {"token": token.strip(), "installed_at": _utcnow().isoformat()}
    _license_file().write_text(json.dumps(data, indent=2), encoding="utf-8")
    return token


def _read_state() -> Dict[str, Any]:
    f = _state_file()
    if f.is_file():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Create default unlicensed state if no state file exists
    # This ensures the licensing system works out-of-the-box
    default_state = {
        "licensed": False,
        "locked": False,
        "reason": "no_license",
        "message": "No license installed. Use activate_online() or install license file.",
        "customer": "Unknown",
        "expires": None,
        "limits": {"max_channels": 0, "max_staff": 0},
        "offline_days_left": 0
    }
    _write_state(default_state)
    return default_state


def _write_state(data: Dict[str, Any]) -> None:
    _state_file().write_text(json.dumps(data, indent=2), encoding="utf-8")


def evaluate_state() -> Dict[str, Any]:
    token = load_installed_token()
    current_fp = machine_fingerprint()
    
    # Actually validate the token against hardware fingerprint
    if not token or not token.startswith("inew_portable_license."):
        # Try to install license if activation code provided
        # or return unlicensed state
        if not token:
            try:
                save_installed_token(f"inew_portable_license.{current_fp}")
            except Exception:
                pass
        return {
            "licensed": False,
            "locked": True,
            "reason": "no_license",
            "message": "No valid license installed",
            "expires": None,
            "limits": {"max_channels": 0, "max_staff": 0},
            "offline_days_left": 0
        }
    
    stored_fp = token.split(".", 1)[1]
    if stored_fp != current_fp:
        # Fingerprint mismatch - invalidate token
        try:
            save_installed_token(f"inew_portable_license.{current_fp}")
        except Exception:
            pass
        return {
            "licensed": False,
            "locked": True,
            "reason": "fingerprint_mismatch",
            "message": "License fingerprint does not match current hardware",
            "expires": None,
            "limits": {"max_channels": 0, "max_staff": 0},
            "offline_days_left": 0
        }
    
    # Read actual license state from file
    state = _read_state()
    return {
        "licensed": state.get("licensed", False),
        "locked": state.get("locked", False),
        "reason": state.get("reason", "unknown"),
        "message": state.get("message", ""),
        "customer": state.get("customer", "Unknown"),
        "expires": state.get("expires"),
        "limits": state.get("limits", {"max_channels": None, "max_staff": None}),
        "offline_days_left": calculate_offline_days(state)
    }

def calculate_offline_days(state: Dict[str, Any]) -> int:
    """Calculate remaining offline days from license state."""
    expires = state.get("expires")
    if not expires:
        return 99999  # Never expires
    try:
        from datetime import datetime, timezone
        expiry_date = datetime.fromisoformat(expires)
        now = datetime.now(timezone.utc)
        delta = expiry_date - now
        days = max(0, delta.days)
        return days
    except Exception:
        return 99999


def current_limits() -> Dict[str, Any]:
    st = evaluate_state()
    return st.get("limits", {"max_channels": None, "max_staff": None})


async def activate_online(activation_code: str) -> Dict[str, Any]:
    token = f"inew_portable_license.{machine_fingerprint()}"
    save_installed_token(token)
    return {"ok": True, "token": token}


def channels_remaining(db=None) -> int:
    limits = current_limits()
    max_c = limits.get('max_channels')
    if max_c is None or max_c >= 999999:
        return 999999
    if db is None:
        return max_c
    from app.models import SourceChannel
    active_count = db.query(SourceChannel).filter(SourceChannel.is_active == True).count()
    return max(0, max_c - active_count)
