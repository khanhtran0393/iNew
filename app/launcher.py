import os
import sys
import time
import socket
import asyncio
import webbrowser
import threading
from pathlib import Path
from PIL import Image
import uvicorn
from app.config import settings
from app.resources import get_asset_path
from app.main import app as fastapi_app


def _port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def _open_browser_when_ready(url: str, port: int) -> None:
    for _ in range(50):
        time.sleep(0.2)
        if _port_in_use(port):
            webbrowser.open(url)
            break


def _make_tray(stop_event: threading.Event):
    try:
        import pystray
        tray_img_path = get_asset_path("app/web/static/img/tray.png")
        if not tray_img_path.is_file():
            img = Image.new("RGBA", (64, 64), color=(34, 158, 217, 255))
        else:
            img = Image.open(tray_img_path)

        def on_open(icon, item):
            webbrowser.open(f"http://127.0.0.1:{settings.PORT}")

        def on_exit(icon, item):
            icon.stop()
            stop_event.set()
            os._exit(0)

        menu = pystray.Menu(
            pystray.MenuItem("Mở iNew", on_open, default=True),
            pystray.MenuItem("Thoát", on_exit)
        )
        icon = pystray.Icon("iNew", img, "iNew - Tin tức đa nền tảng", menu)
        icon.run()
    except Exception as e:
        print(f"Tray icon warning: {e}")


def _prepare_environment() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.raw_media_dir.mkdir(parents=True, exist_ok=True)
    settings.edited_media_dir.mkdir(parents=True, exist_ok=True)
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    settings.final_outputs_dir.mkdir(parents=True, exist_ok=True)
    settings.voices_dir.mkdir(parents=True, exist_ok=True)
    settings.lipsync_dir.mkdir(parents=True, exist_ok=True)
    settings.avatars_dir.mkdir(parents=True, exist_ok=True)


def serve() -> None:
    _prepare_environment()
    url = f"http://127.0.0.1:{settings.PORT}"
    threading.Thread(target=_open_browser_when_ready, args=(url, settings.PORT), daemon=True).start()

    stop_event = threading.Event()
    if os.name == "nt":
        threading.Thread(target=_make_tray, args=(stop_event,), daemon=True).start()

    config = uvicorn.Config(
        fastapi_app,
        host=settings.HOST,
        port=settings.PORT,
        log_level="info",
        reload=False
    )
    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    serve()
