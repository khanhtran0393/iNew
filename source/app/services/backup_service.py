"""Automated database and media backup service."""

import asyncio
import shutil
from datetime import datetime
from app.config import settings


def create_backup() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = settings.backup_dir / f"backup_{ts}.sqlite"
    db_file = Path(settings.DATABASE_URL.replace("sqlite:///", ""))
    if db_file.exists():
        shutil.copy2(db_file, backup_file)
        return str(backup_file)
    return ""


async def backup_worker_loop():
    while True:
        try:
            await asyncio.sleep(settings.BACKUP_INTERVAL_HOURS * 3600)
            create_backup()
        except Exception:
            break
