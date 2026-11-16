"""Desktop launcher with system tray integration and auto-browser opening."""

import os
import sys
import threading
import time
import uvicorn
from pathlib import Path

from app.config import settings
from app.services.desktop import pick_port, open_browser


def _prepare_environment():
    ffmpeg_dir = Path(r"D:\iNew-Setup-1.0.5\source\ffmpeg")
    if ffmpeg_dir.exists():
        os.environ["PATH"] = str(ffmpeg_dir) + os.path.pathsep + os.environ.get("PATH", "")
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["HF_HUB_DISABLE_XET"] = "1"


def main():
    _prepare_environment()
    port = pick_port(settings.PORT, settings.HOST)
    url = f"http://localhost:{port}"

    def run_server():
        uvicorn.run("app.main:app", host=settings.HOST, port=port, log_level="info")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    time.sleep(2)
    if "INEW_NO_BROWSER" not in os.environ:
        open_browser(url)

    print(f"\n[*] {settings.APP_NAME} v{settings.APP_VERSION} đang chạy tại: {url}")
    print(f"[*] Thư mục dữ liệu: {settings.data_dir}")
    print("[*] Nhấn Ctrl+C để dừng ứng dụng.\n")

    try:
        while server_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nĐang dừng iNew...")


if __name__ == "__main__":
    main()
