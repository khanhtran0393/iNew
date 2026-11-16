"""Runtime configuration persistence and dynamic updates."""

import json
from app.database import SessionLocal
from app.models import AppSetting
from app.config import settings


def apply_saved_config() -> list:
    """Load settings from database and override runtime settings."""
    db = SessionLocal()
    applied = []
    try:
        items = db.query(AppSetting).all()
        for item in items:
            if hasattr(settings, item.key):
                orig_type = type(getattr(settings, item.key))
                try:
                    if orig_type == bool:
                        val = item.value.lower() in ("true", "1", "yes")
                    elif orig_type == int:
                        val = int(item.value)
                    elif orig_type == float:
                        val = float(item.value)
                    else:
                        val = item.value
                    setattr(settings, item.key, val)
                    applied.append(item.key)
                except Exception:
                    pass
    finally:
        db.close()
    return applied


def ensure_setup_flag() -> bool:
    db = SessionLocal()
    try:
        row = db.query(AppSetting).filter(AppSetting.key == "setup_completed").first()
        return bool(row and row.value == "true")
    finally:
        db.close()
