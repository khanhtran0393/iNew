"""Application Settings and Environment Configuration."""

import os
import sys
import secrets
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_default_data_root() -> str:
    """Return default data root directory according to platform."""
    if sys.platform == "win32":
        for candidate in ["D:\\AK_News_Data", "C:\\AK_News_Data"]:
            drive = candidate[:3]
            if os.path.exists(drive):
                return candidate
        return os.path.join(os.path.expanduser("~"), "AK_News_Data")
    return os.path.expanduser("~/ak_news_data")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "iNew - Hệ Thống Tin Tức Đa Nền Tảng"
    APP_ENV: str = "production"
    DEBUG: bool = False
    SECRET_KEY: str = "ak-news-super-secret-key-change-in-production-2026"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DATA_ROOT_PATH: str = ""

    # Database
    DATABASE_URL: str = "sqlite:///./data/ak_news.db"
    POSTGRES_USER: str = "ak_news_user"
    POSTGRES_PASSWORD: str = "ak_news_password_2026"
    POSTGRES_DB: str = "ak_news_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    REDIS_URL: str = "redis://localhost:6379/0"

    # Telegram
    TELEGRAM_API_ID: int = 0
    TELEGRAM_API_HASH: str = ""
    TELEGRAM_PHONE: str = ""
    TELEGRAM_SESSION_NAME: str = "ak_news_telethon"
    TELEGRAM_SESSION_STRING: str = ""
    TELEGRAM_FLOOD_SLEEP_THRESHOLD: int = 60
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_DEFAULT_EDITORIAL_CHAT_ID: int = 0
    MAX_MEDIA_DOWNLOAD_SIZE_MB: int = 50
    ALBUM_BUFFER_SECONDS: float = 3.0

    # System & Dedup
    DISK_WATCHDOG_THRESHOLD_PERCENT: float = 90.0
    DEDUP_WINDOW_HOURS: int = 24
    DEDUP_FUZZY_THRESHOLD: float = 0.85
    ENABLE_SEMANTIC_DEDUP: bool = True

    # AI
    AI_ENABLED: bool = True
    AI_PROVIDER: str = "gemini"
    AI_API_KEY: str = ""
    AI_MODEL: str = "gemini-3.8-flash"
    AI_FALLBACK_MODEL: str = "gemini-3.5-flash-lite"
    AI_DAILY_LIMIT_PER_USER: int = 100
    AI_DAILY_LIMIT_TOTAL: int = 1000
    AI_MAX_INPUT_CHARS: int = 20000
    ARTICLE_FULLTEXT_ENABLED: bool = True
    AI_VISION_MODEL: str = "gemini-3.8-flash"
    AI_VIDEO_MAX_MB: int = 25
    AI_IMAGE_MAX_SIDE: int = 1024
    AI_MEDIA_MAX_OUTPUT_TOKENS: int = 2048

    # Admin & Auth
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123456"
    ADMIN_FULL_NAME: str = "Quản Trị Viên Hệ Thống"
    PUBLIC_BASE_URL: str = ""
    COOKIE_SECURE: bool = False
    LOGIN_MAX_FAILURES: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15
    SEED_DEMO_DATA: bool = False

    # Schedules & Maintenance
    TELEGRAM_CATCHUP_INTERVAL_MINUTES: int = 15
    TELEGRAM_CATCHUP_MAX_PER_CHANNEL: int = 50
    TELEGRAM_ONLINE_PING_SECONDS: int = 30
    MAX_MANUAL_DOWNLOAD_SIZE_MB: int = 100
    BACKUP_INTERVAL_HOURS: int = 24
    BACKUP_KEEP_DAYS: int = 7

    # Voice & Media
    TTS_VOICE: str = "vi-VN-HoaiMyNeural"
    VOICE_ENGINE_MODE: str = "v3turbo"
    VOICE_ENGINE_PRECISION: str = "fp32"
    VOICE_MAX_TEXT_CHARS: int = 5000
    VOICE_REF_MIN_SECONDS: float = 3.0
    VOICE_REF_MAX_SECONDS: float = 30.0
    VOICE_REF_MAX_UPLOAD_MB: int = 20
    VOICE_OUTPUT_RETENTION_DAYS: int = 30
    ARCHIVE_AFTER_DAYS: int = 30
    MEDIA_RETENTION_DAYS: int = 14
    GENERATED_VIDEO_RETENTION_DAYS: int = 30
    MEDIA_RETENTION_EMERGENCY_DAYS: int = 3
    DISK_ALERT_CHAT_ID: int = 0

    # Application Metadata & Licensing
    APP_VERSION: str = "1.0.5"
    KEY_BOT_USERNAME: str = "Kichhoatkey_bot"
    UPDATE_REPO: str = "dienmoc86/iNew-releases"
    ALLOW_LAN: bool = True
    LICENSE_PUBLIC_KEY: str = ""
    LICENSE_KEY: str = ""
    LICENSE_SERVER_URL: str = ""
    LICENSE_ENFORCE: bool = False

    @property
    def data_dir(self) -> Path:
        root = Path(self.DATA_ROOT_PATH if self.DATA_ROOT_PATH else get_default_data_root())
        root.mkdir(parents=True, exist_ok=True)
        return root

    @property
    def raw_media_dir(self) -> Path:
        p = self.data_dir / "raw_media"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def edited_media_dir(self) -> Path:
        p = self.data_dir / "edited_media"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def backup_dir(self) -> Path:
        p = self.data_dir / "backup"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def final_outputs_dir(self) -> Path:
        p = self.data_dir / "final_outputs"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def voices_dir(self) -> Path:
        p = self.data_dir / "voices"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def lipsync_dir(self) -> Path:
        p = self.data_dir / "lipsync"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def avatars_dir(self) -> Path:
        p = self.data_dir / "avatars"
        p.mkdir(parents=True, exist_ok=True)
        return p


WEAK_DEFAULT_PASSWORDS = ["admin123456", "editor123"]


def _ensure_secret_key(settings_obj: Settings):
    secret_file = settings_obj.data_dir / ".secret_key"
    if secret_file.is_file():
        try:
            val = secret_file.read_text(encoding="utf-8").strip()
            if val:
                settings_obj.SECRET_KEY = val
                return
        except Exception:
            pass
    val = secrets.token_urlsafe(32)
    try:
        secret_file.write_text(val, encoding="utf-8")
        settings_obj.SECRET_KEY = val
    except Exception:
        pass


settings = Settings()
_ensure_secret_key(settings)
