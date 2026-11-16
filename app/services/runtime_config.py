from app.database import SessionLocal
from app.models import AppSetting


def _get(key: str, default: str = "") -> str:
    db = SessionLocal()
    try:
        s = db.query(AppSetting).filter_by(key=key).first()
        return s.value if s else default
    finally:
        db.close()


def _set(key: str, value: str) -> None:
    db = SessionLocal()
    try:
        s = db.query(AppSetting).filter_by(key=key).first()
        if s:
            s.value = value
        else:
            db.add(AppSetting(key=key, value=value))
        db.commit()
    finally:
        db.close()


def setup_completed() -> bool:
    return _get("setup_completed", "false").lower() == "true"


def mark_setup_completed() -> None:
    _set("setup_completed", "true")


def ensure_setup_flag() -> None:
    if not setup_completed():
        pass


def save_config(key: str, value: str) -> None:
    _set(key, value)


def apply_saved_config() -> None:
    from app.config import settings
    db = SessionLocal()
    try:
        settings_rows = db.query(AppSetting).all()
        for s in settings_rows:
            k = s.key
            v = s.value or ""
            if k == "app_name" and v:
                settings.APP_NAME = v
            elif k == "allow_lan":
                settings.ALLOW_LAN = (v.lower() == "true")
            elif k == "ai_enabled":
                settings.AI_ENABLED = (v.lower() == "true")
            elif k == "ai_model" and v:
                settings.AI_MODEL = v
            elif k == "tts_voice" and v:
                settings.TTS_VOICE = v
            elif k == "dedup_threshold" and v:
                try:
                    settings.DEDUP_FUZZY_THRESHOLD = int(v)
                except ValueError:
                    pass
    except Exception:
        pass
    finally:
        db.close()
