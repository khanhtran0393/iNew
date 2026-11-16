import os
import sys
import json
import socket
import logging
import webbrowser
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.config import settings

logger = logging.getLogger("ak_news.desktop")

DEFAULT_PORT = 8000
DESKTOP_CONFIG_NAME = "desktop.json"


def get_desktop_config_path() -> Path:
    return settings.data_dir / DESKTOP_CONFIG_NAME


def read_desktop_config() -> Dict[str, Any]:
    cfg_path = get_desktop_config_path()
    if cfg_path.exists():
        try:
            return json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to read desktop config: {e}")
    return {"allow_lan": False, "port": DEFAULT_PORT, "auto_open_browser": True}


def write_desktop_config(cfg: Dict[str, Any]) -> None:
    cfg_path = get_desktop_config_path()
    try:
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to write desktop config: {e}")


def currently_lan() -> bool:
    env_val = os.environ.get("INEW_BOUND_HOST", "")
    if env_val in ("0.0.0.0", "*"):
        return True
    cfg = read_desktop_config()
    return bool(cfg.get("allow_lan", settings.ALLOW_LAN))


def set_allow_lan(enabled: bool) -> None:
    settings.ALLOW_LAN = enabled
    cfg = read_desktop_config()
    cfg["allow_lan"] = enabled
    write_desktop_config(cfg)
    logger.info(f"LAN access setting changed to: {enabled}")


def lan_addresses() -> List[str]:
    """Discover all non-loopback local network IP addresses."""
    addresses = []
    try:
        # Standard UDP socket trick to get primary outbound IP without sending data
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        try:
            s.connect(("10.255.255.255", 1))
            primary_ip = s.getsockname()[0]
            if primary_ip and not primary_ip.startswith("127."):
                addresses.append(primary_ip)
        except Exception:
            pass
        finally:
            s.close()
    except Exception:
        pass

    # Hostname fallback
    try:
        host_name = socket.gethostname()
        for ip in socket.gethostbyname_ex(host_name)[2]:
            if not ip.startswith("127.") and ip not in addresses:
                addresses.append(ip)
    except Exception:
        pass

    if not addresses:
        addresses.append("127.0.0.1")
    return addresses


def get_server_port() -> int:
    env_port = os.environ.get("INEW_PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            pass
    cfg = read_desktop_config()
    return int(cfg.get("port", DEFAULT_PORT))


def open_browser(port: Optional[int] = None) -> None:
    p = port or get_server_port()
    url = f"http://127.0.0.1:{p}/"
    logger.info(f"Opening default browser at {url}")
    try:
        webbrowser.open(url)
    except Exception as e:
        logger.warning(f"Could not open browser automatically: {e}")


def request_restart() -> None:
    restart_flag = settings.data_dir / ".restart_pending"
    try:
        restart_flag.write_text("1", encoding="utf-8")
        logger.info("Restart request flag written.")
    except Exception as e:
        logger.error(f"Failed to write restart flag: {e}")
