import os
import sys
import json
import shutil
import zipfile
import platform
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from app.config import settings
from app.services.proc import FFMPEG_BIN, FFPROBE_BIN, run

logger = logging.getLogger("ak_news.diagnostics")

LOG_TAIL_BYTES = 65536
MAX_LOG_FILES = 10


def check_ffmpeg_presence() -> Dict[str, Any]:
    res = {"ffmpeg_available": False, "ffprobe_available": False, "ffmpeg_version": "", "path": FFMPEG_BIN}
    try:
        proc = run([FFMPEG_BIN, "-version"])
        if proc.returncode == 0:
            res["ffmpeg_available"] = True
            res["ffmpeg_version"] = proc.stdout.splitlines()[0] if proc.stdout else ""
    except Exception as e:
        res["ffmpeg_error"] = str(e)

    try:
        proc2 = run([FFPROBE_BIN, "-version"])
        if proc2.returncode == 0:
            res["ffprobe_available"] = True
    except Exception as e:
        res["ffprobe_error"] = str(e)

    return res


def get_system_diagnostics() -> Dict[str, Any]:
    # Disk space check
    data_root = settings.data_dir
    total_b, used_b, free_b = 0, 0, 0
    try:
        usage = shutil.disk_usage(data_root)
        total_b, used_b, free_b = usage.total, usage.used, usage.free
    except Exception:
        pass

    # DB stats
    db_size = 0
    db_file = data_root / "ak_news.db"
    if db_file.exists():
        db_size = db_file.stat().st_size

    # Python & OS environment
    info = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "app_name": settings.APP_NAME,
        "app_version": settings.VERSION,
        "platform": sys.platform,
        "os_version": platform.platform(),
        "python_version": sys.version,
        "executable": sys.executable,
        "data_dir": str(settings.data_dir),
        "db_size_bytes": db_size,
        "disk_total_gb": round(total_b / (1024**3), 2),
        "disk_free_gb": round(free_b / (1024**3), 2),
        "ffmpeg_status": check_ffmpeg_presence(),
        "allow_lan": settings.ALLOW_LAN,
    }
    return info


def tail_app_logs(max_lines: int = 150) -> List[str]:
    log_dir = settings.data_dir / "logs"
    if not log_dir.exists():
        return ["No log directory found."]

    log_files = sorted(log_dir.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not log_files:
        return ["No log files available."]

    latest_log = log_files[0]
    lines = []
    try:
        with open(latest_log, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return [l.rstrip("\r\n") for l in lines[-max_lines:]]
    except Exception as e:
        return [f"Failed to read log {latest_log.name}: {e}"]


def build_zip() -> Path:
    out_zip = settings.data_dir / "diagnostics.zip"
    diag_data = get_system_diagnostics()

    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Write JSON diagnostic info
        zf.writestr("diagnostics.json", json.dumps(diag_data, indent=2))

        # Include recent logs
        log_dir = settings.data_dir / "logs"
        if log_dir.exists():
            for lf in sorted(log_dir.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)[:MAX_LOG_FILES]:
                try:
                    zf.write(lf, arcname=f"logs/{lf.name}")
                except Exception:
                    pass

    return out_zip
