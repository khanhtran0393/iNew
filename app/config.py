import os
import secrets
from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_default_data_root() -> Path:
    """Determine default data root depending on OS drive availability."""
    if os.name == "nt":
        if os.path.exists("D:\\"):
            return Path("D:\\AK_News_Data")
        return Path("C:\\AK_News_Data")
    linux_data_dir = Path.home() / ".local" / "share" / "ak_news"
    return linux_data_dir


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "iNew - Hệ Thống Tin Tức Đa Nền Tảng"
    APP_VERSION: str = "1.0.0"
    VERSION: str = "1.0.0"
    APP_ENV: str = "production"
    DEBUG: bool = False

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    ALLOW_LAN: bool = True

    DEFAULT_SECRET_KEY: str = "ak-news-super-secret-key-change-in-production-2026"
    SECRET_KEY: str = ""
    COOKIE_SECURE: bool = False

    DATA_ROOT_PATH: Optional[Path] = None

    DATABASE_URL: str = "sqlite:///./data/ak_news.db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "ak_news"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Default Admin
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123456"
    ADMIN_FULL_NAME: str = "Quản Trị Viên Hệ Thống"
    WEAK_DEFAULT_PASSWORDS: List[str] = ["admin123456", "editor123"]

    LOGIN_MAX_FAILURES: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    # Telegram Credentials & Scraper Settings
    TELEGRAM_API_ID: str = ""
    TELEGRAM_API_HASH: str = ""
    TELEGRAM_PHONE: str = ""
    TELEGRAM_SESSION_NAME: str = "ak_news_session"
    TELEGRAM_SESSION_STRING: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_DEFAULT_EDITORIAL_CHAT_ID: str = ""
    TELEGRAM_ONLINE_PING_SECONDS: int = 30
    TELEGRAM_FLOOD_SLEEP_THRESHOLD: int = 60
    TELEGRAM_CATCHUP_INTERVAL_MINUTES: int = 30
    TELEGRAM_CATCHUP_MAX_PER_CHANNEL: int = 50
    ALBUM_BUFFER_SECONDS: int = 5

    # AI Configurations
    AI_ENABLED: bool = True
    AI_PROVIDER: str = "gemini"
    AI_API_KEY: str = ""
    AI_MODEL: str = "gemini-2.5-flash"
    AI_FALLBACK_MODEL: str = "gemini-2.5-pro"
    AI_VISION_MODEL: str = "gemini-2.5-flash"
    AI_DAILY_LIMIT_PER_USER: int = 100
    AI_DAILY_LIMIT_TOTAL: int = 1000
    AI_MAX_INPUT_CHARS: int = 10000
    AI_IMAGE_MAX_SIDE: int = 1920
    AI_VIDEO_MAX_MB: int = 100
    AI_MEDIA_MAX_OUTPUT_TOKENS: int = 2048

    # Dedup & Retention
    DEDUP_WINDOW_HOURS: int = 48
    DEDUP_FUZZY_THRESHOLD: int = 85
    ENABLE_SEMANTIC_DEDUP: bool = True
    ARTICLE_FULLTEXT_ENABLED: bool = True
    ARCHIVE_AFTER_DAYS: int = 30
    MEDIA_RETENTION_DAYS: int = 30
    MEDIA_RETENTION_EMERGENCY_DAYS: int = 7
    GENERATED_VIDEO_RETENTION_DAYS: int = 30
    MAX_MEDIA_DOWNLOAD_SIZE_MB: int = 500
    MAX_MANUAL_DOWNLOAD_SIZE_MB: int = 200

    # Voice Studio
    TTS_VOICE: str = "vi-VN-HoaiMyNeural"
    VOICE_ENGINE_MODE: str = "v3turbo"
    VOICE_ENGINE_PRECISION: str = "fp32"
    VOICE_MAX_TEXT_CHARS: int = 2000
    VOICE_REF_MIN_SECONDS: int = 3
    VOICE_REF_MAX_SECONDS: int = 30
    VOICE_REF_MAX_UPLOAD_MB: int = 20
    VOICE_OUTPUT_RETENTION_DAYS: int = 30

    # System, Backup & Watchdog
    BACKUP_INTERVAL_HOURS: int = 24
    BACKUP_KEEP_DAYS: int = 7
    DISK_WATCHDOG_THRESHOLD_PERCENT: int = 90
    DISK_ALERT_CHAT_ID: str = ""
    SEED_DEMO_DATA: bool = False
    UPDATE_REPO: str = "dienmoc86/iNew-releases"

    # Licensing
    LICENSE_ENFORCE: bool = True
    LICENSE_SERVER_URL: str = ""
    LICENSE_PUBLIC_KEY: str = ""
    LICENSE_KEY: str = ""
    KEY_BOT_USERNAME: str = ""

    @property
    def app_dir(self) -> Path:
        return Path(__file__).resolve().parent

    @property
    def GEMINI_API_KEY(self) -> str:
        return self.AI_API_KEY if self.AI_PROVIDER == "gemini" else os.environ.get("GEMINI_API_KEY", self.AI_API_KEY)

    @property
    def OPENAI_API_KEY(self) -> str:
        return self.AI_API_KEY if self.AI_PROVIDER == "openai" else os.environ.get("OPENAI_API_KEY", "")

    @property
    def POLLINATIONS_API_KEY(self) -> str:
        return self.AI_API_KEY if self.AI_PROVIDER == "pollinations" else os.environ.get("POLLINATIONS_API_KEY", "")

    @property
    def data_dir(self) -> Path:
        if self.DATA_ROOT_PATH:
            p = self.DATA_ROOT_PATH
        else:
            p = get_default_data_root()
        p.mkdir(parents=True, exist_ok=True)
        return p

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
        p = self.data_dir / "backups"
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


def _ensure_secret_key(settings: Settings) -> None:
    if settings.SECRET_KEY and settings.SECRET_KEY != settings.DEFAULT_SECRET_KEY:
        return
    key_file = settings.data_dir / ".secret_key"
    if key_file.is_file():
        k = key_file.read_text(encoding="utf-8").strip()
        if k:
            settings.SECRET_KEY = k
            return
    new_key = secrets.token_urlsafe(32)
    key_file.write_text(new_key, encoding="utf-8")
    settings.SECRET_KEY = new_key


settings = Settings()
_ensure_secret_key(settings)
