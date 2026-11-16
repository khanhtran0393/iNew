"""Benchmark and system health reporting utilities."""

from datetime import datetime, timezone, timedelta
from app.database import SessionLocal
from app.models import SourceChannel, _utcnow


def _v(value, unit=""):
    return f"{value} {unit}".strip() if value is not None else "—"


def _verdict(ok: bool) -> str:
    return "ĐẠT" if ok else "CHƯA ĐẠT"


def build_report(hours: int = 24) -> dict:
    db = SessionLocal()
    try:
        now = _utcnow()
        started = now - timedelta(hours=hours)
        channels = db.query(SourceChannel).filter(SourceChannel.source_type == "telegram", SourceChannel.is_deleted == False).all()

        return {
            "hours_run": hours,
            "channels_count": len(channels),
            "generated_at": now.isoformat(),
            "overall_status": "OK",
            "channels": [
                {
                    "id": c.id,
                    "title": c.title,
                    "last_fetched": c.last_fetched_at.isoformat() if c.last_fetched_at else None,
                    "error_count": c.error_count
                }
                for c in channels
            ]
        }
    finally:
        db.close()
