import os
from pathlib import Path

app_dir = Path("app")

# 1. app/config.py
config_code = '''import os
import secrets
from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_default_data_root() -> Path:
    """Determine default data root depending on OS drive availability."""
    if os.name == "nt":
        if os.path.exists("D:\\\\"):
            return Path("D:\\\\AK_News_Data")
        return Path("C:\\\\AK_News_Data")
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
'''

(app_dir / "config.py").write_text(config_code, encoding="utf-8")

# 2. app/models.py
models_code = '''import json
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from sqlalchemy import (
    BigInteger, Boolean, DateTime, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class RawPostStatus(str, Enum):
    NEW = "new"
    DUPLICATE = "duplicate"
    READY = "ready"
    REJECTED = "rejected"


class WorkflowStatus(str, Enum):
    CLAIMED = "claimed"
    VERIFYING = "verifying"
    EDITING = "editing"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    ARCHIVED = "archived"


class RoleSlug(str, Enum):
    ADMIN = "admin"
    LEAD = "lead"
    EDITOR = "editor"
    MONITOR = "monitor"
    VIEWER = "viewer"


class MediaType(str, Enum):
    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"
    UNKNOWN = "unknown"


class MediaOrigin(str, Enum):
    SOURCE = "source"
    MANUAL = "manual"


class OutboxStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    permissions_json: Mapped[str] = mapped_column(Text, default="[]")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    users: Mapped[List["User"]] = relationship("User", back_populates="role")

    @property
    def permissions(self) -> List[str]:
        try:
            return json.loads(self.permissions_json or "[]")
        except Exception:
            return []


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"), nullable=False)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    role: Mapped["Role"] = relationship("Role", back_populates="users")
    assigned_posts: Mapped[List["RawPost"]] = relationship("RawPost", back_populates="assigned_user")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    topic_sources: Mapped[List["TopicSource"]] = relationship("TopicSource", back_populates="topic", cascade="all, delete-orphan")


class SourceChannel(Base):
    __tablename__ = "source_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="telegram")  # telegram, rss, web
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    rss_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    telegram_channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    quota_mb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    used_mb: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    topic_sources: Mapped[List["TopicSource"]] = relationship("TopicSource", back_populates="source_channel", cascade="all, delete-orphan")
    posts: Mapped[List["RawPost"]] = relationship("RawPost", back_populates="source_channel")


class TopicSource(Base):
    __tablename__ = "topic_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[int] = mapped_column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False)
    source_channel_id: Mapped[int] = mapped_column(Integer, ForeignKey("source_channels.id", ondelete="CASCADE"), nullable=False)

    topic: Mapped["Topic"] = relationship("Topic", back_populates="topic_sources")
    source_channel: Mapped["SourceChannel"] = relationship("SourceChannel", back_populates="topic_sources")


class EditorialGroup(Base):
    __tablename__ = "editorial_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class RawPost(Base):
    __tablename__ = "raw_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_channel_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("source_channels.id"), nullable=True)
    channel_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    original_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    edited_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    text_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    media_group_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default=RawPostStatus.NEW.value, index=True)
    workflow_status: Mapped[str] = mapped_column(String(50), default=WorkflowStatus.CLAIMED.value, index=True)
    assigned_to: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    source_channel: Mapped[Optional["SourceChannel"]] = relationship("SourceChannel", back_populates="posts")
    assigned_user: Mapped[Optional["User"]] = relationship("User", back_populates="assigned_posts")
    media_items: Mapped[List["MediaItem"]] = relationship("MediaItem", back_populates="raw_post", cascade="all, delete-orphan")
    edit_histories: Mapped[List["RawPostEditHistory"]] = relationship("RawPostEditHistory", back_populates="raw_post", cascade="all, delete-orphan")
    audit_logs: Mapped[List["WorkflowAuditLog"]] = relationship("WorkflowAuditLog", back_populates="raw_post", cascade="all, delete-orphan")


class MediaItem(Base):
    __tablename__ = "media_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_post_id: Mapped[int] = mapped_column(Integer, ForeignKey("raw_posts.id", ondelete="CASCADE"), nullable=False)
    media_type: Mapped[str] = mapped_column(String(50), default=MediaType.PHOTO.value)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_sha256: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    origin: Mapped[str] = mapped_column(String(50), default=MediaOrigin.SOURCE.value)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    raw_post: Mapped["RawPost"] = relationship("RawPost", back_populates="media_items")


class RawPostEditHistory(Base):
    __tablename__ = "raw_post_edit_histories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_post_id: Mapped[int] = mapped_column(Integer, ForeignKey("raw_posts.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    old_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    raw_post: Mapped["RawPost"] = relationship("RawPost", back_populates="edit_histories")


class WorkflowAuditLog(Base):
    __tablename__ = "workflow_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_post_id: Mapped[int] = mapped_column(Integer, ForeignKey("raw_posts.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    raw_post: Mapped["RawPost"] = relationship("RawPost", back_populates="audit_logs")


class OutboxNotification(Base):
    __tablename__ = "outbox_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    raw_post_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("raw_posts.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=OutboxStatus.PENDING.value)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class AiApiKey(Base):
    __tablename__ = "ai_api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class AiTaskRoute(Base):
    __tablename__ = "ai_task_routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    custom_system_instruction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AiUsageLog(Base):
    __tablename__ = "ai_usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    task: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class PublishTarget(Base):
    __tablename__ = "publish_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)  # facebook, telegram, tiktok, youtube
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_config: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class PublishLog(Base):
    __tablename__ = "publish_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    publish_target_id: Mapped[int] = mapped_column(Integer, ForeignKey("publish_targets.id"), nullable=False)
    raw_post_id: Mapped[int] = mapped_column(Integer, ForeignKey("raw_posts.id"), nullable=False)
    external_post_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class SystemMetric(Base):
    __tablename__ = "system_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class ActionLog(Base):
    __tablename__ = "action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class GeneratedVideo(Base):
    __tablename__ = "generated_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_post_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("raw_posts.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    output_path: Mapped[str] = mapped_column(String(500), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    voice_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class VoiceProfile(Base):
    __tablename__ = "voice_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    speaker_name: Mapped[str] = mapped_column(String(150), nullable=False)
    gender: Mapped[str] = mapped_column(String(20), default="female")
    reference_path: Mapped[str] = mapped_column(String(500), nullable=False)
    reference_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    consent_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class VoiceJob(Base):
    __tablename__ = "voice_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    voice_key: Mapped[str] = mapped_column(String(100), nullable=False)
    voice_label: Mapped[str] = mapped_column(String(150), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    speed: Mapped[float] = mapped_column(Float, default=1.0)
    expressiveness: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(String(50), default="queued")
    output_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    render_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class LipsyncJob(Base):
    __tablename__ = "lipsync_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_media_path: Mapped[str] = mapped_column(String(500), nullable=False)
    audio_path: Mapped[str] = mapped_column(String(500), nullable=False)
    talking_photo: Mapped[bool] = mapped_column(Boolean, default=True)
    layout: Mapped[str] = mapped_column(String(50), default="pip_bottom_right")
    engine: Mapped[str] = mapped_column(String(50), default="local")
    status: Mapped[str] = mapped_column(String(50), default="queued")
    output_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
'''

(app_dir / "models.py").write_text(models_code, encoding="utf-8")
print("Generated config.py and models.py")
