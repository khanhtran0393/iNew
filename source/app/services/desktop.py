"""Desktop integration utilities, port checking and system status."""

import socket
import webbrowser
from app.config import settings


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def pick_port(wanted_port: int, host: str = "0.0.0.0") -> int:
    port = wanted_port
    while is_port_in_use(port, "127.0.0.1"):
        port += 1
    return port


def open_browser(url: str):
    try:
        webbrowser.open(url)
    except Exception:
        pass
