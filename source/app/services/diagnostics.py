"""System diagnostics, disk monitoring and hardware metrics."""

import shutil
import psutil
from typing import Dict, Any
from app.config import settings


def get_system_diagnostics() -> Dict[str, Any]:
    disk = shutil.disk_usage(str(settings.data_dir))
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_total_gb": round(disk.total / (1024**3), 2),
        "disk_used_gb": round(disk.used / (1024**3), 2),
        "disk_free_gb": round(disk.free / (1024**3), 2),
        "disk_used_percent": round((disk.used / disk.total) * 100, 1),
    }
