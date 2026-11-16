import os
import json
from pathlib import Path
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from sqlalchemy import (
    BigInteger, Boolean, DateTime, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym
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

    def __eq__(self, other):
        if isinstance(other, str):
            return self.slug == other or self.name == other
        return super().__eq__(other)

    def __str__(self):
        return self.slug or self.name

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
    telegram_user_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    role: Mapped["Role"] = relationship("Role", back_populates="users")
    assigned_posts: Mapped[List["RawPost"]] = relationship("RawPost", back_populates="assigned_user")

    @property
    def role_slug(self) -> str:
        return self.role.slug if self.role else ""

    @property
    def is_admin(self) -> bool:
        return self.role_slug == "admin"

    @property
    def is_lead(self) -> bool:
        return self.role_slug in ("admin", "lead")

    @property
    def is_editor(self) -> bool:
        return self.role_slug in ("admin", "lead", "editor")


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

    enabled = synonym("is_active")
    source_identifier = synonym("url")
    storage_quota_mb = synonym("quota_mb")

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
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    priority: Mapped[str] = mapped_column(String(50), default="NORMAL")
    last_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    topic_sources: Mapped[List["TopicSource"]] = relationship("TopicSource", back_populates="source_channel", cascade="all, delete-orphan")
    posts: Mapped[List["RawPost"]] = relationship("RawPost", back_populates="source_channel")

    def __init__(self, *args, **kwargs):
        username = kwargs.get("username")
        kwargs.pop("used_storage_bytes", None)
        if username and not kwargs.get("url"):
            kwargs["url"] = f"https://t.me/{username.lstrip('@')}"
        elif not username and kwargs.get("url") and "t.me/" in kwargs.get("url"):
            parts = kwargs["url"].rstrip("/").split("/")
            if parts:
                kwargs["username"] = parts[-1].lstrip("@")
        super().__init__(*args, **kwargs)

    @property
    def used_storage_bytes(self) -> int:
        return int((self.used_mb or 0.0) * 1024 * 1024)

    @property
    def topics(self):
        return [ts.topic for ts in self.topic_sources if ts.topic]


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
    article_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    article_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    article_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    editorial_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_source_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    normalized_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at_source: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ingest_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    assigned_user_id = synonym("assigned_to")
    source_id = synonym("source_channel_id")
    telegram_message_id = synonym("channel_message_id")
    cleaned_text = synonym("original_text")
    raw_text = synonym("original_text")
    original_url = synonym("source_url")
    source = synonym("source_channel")

    def __init__(self, *args, **kwargs):
        kwargs.pop("has_media", None)
        kwargs.pop("media_count", None)
        kwargs.pop("is_source_deleted", None)
        super().__init__(*args, **kwargs)

    @property
    def has_media(self) -> bool:
        return bool(self.media_items and len(self.media_items) > 0)

    @has_media.setter
    def has_media(self, val: bool):
        pass

    @property
    def media_count(self) -> int:
        return len(self.media_items) if self.media_items else 0

    @media_count.setter
    def media_count(self, val: int):
        pass

    @property
    def is_source_deleted(self) -> bool:
        return bool(self.source_channel and getattr(self.source_channel, "is_deleted", False))

    @is_source_deleted.setter
    def is_source_deleted(self, val: bool):
        pass

    @property
    def topic_id(self) -> Optional[int]:
        if self.source_channel and getattr(self.source_channel, "topic_sources", None):
            return self.source_channel.topic_sources[0].topic_id
        return None

    @property
    def resolved_text(self) -> str:
        """Nội dung tối ưu nhất để xử lý (AI, Video, Tóm tắt):
        1. edited_text: Nếu đã được biên tập viên chỉnh sửa
        2. article_text: Nếu đã bóc tách toàn văn bài báo thành công
        3. original_text / cleaned_text: Nội dung gốc ban đầu (từ RSS/Telegram)
        """
        return (self.edited_text or self.article_text or self.original_text or "").strip()

    @property
    def dedupe_score(self) -> float:
        return 0.0

    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    source_channel: Mapped[Optional["SourceChannel"]] = relationship("SourceChannel", back_populates="posts")
    assigned_user: Mapped[Optional["User"]] = relationship("User", back_populates="assigned_posts")
    media_items: Mapped[List["MediaItem"]] = relationship("MediaItem", back_populates="raw_post", cascade="all, delete-orphan")
    edit_histories: Mapped[List["RawPostEditHistory"]] = relationship("RawPostEditHistory", back_populates="raw_post", cascade="all, delete-orphan")
    audit_logs: Mapped[List["WorkflowAuditLog"]] = relationship("WorkflowAuditLog", back_populates="raw_post", cascade="all, delete-orphan")
    generated_videos: Mapped[List["GeneratedVideo"]] = relationship("GeneratedVideo", back_populates="raw_post", cascade="all, delete-orphan")


class MediaItem(Base):
    __tablename__ = "media_items"

    local_path = synonym("file_path")
    post_id = synonym("raw_post_id")
    file_size = synonym("file_size_bytes")

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
    remote_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    raw_post: Mapped["RawPost"] = relationship("RawPost", back_populates="media_items")

    def __init__(self, *args, **kwargs):
        remote_url = kwargs.get("remote_url")
        kwargs.pop("is_downloaded", None)
        fname = kwargs.pop("file_name", None)
        dur = kwargs.pop("duration", None)
        if remote_url and not kwargs.get("file_path"):
            kwargs["file_path"] = remote_url
        elif fname and not kwargs.get("file_path"):
            kwargs["file_path"] = fname
        if dur is not None and "duration_seconds" not in kwargs:
            kwargs["duration_seconds"] = dur
        super().__init__(*args, **kwargs)

    @property
    def file_name(self) -> str:
        return Path(self.file_path).name if self.file_path else ""

    @file_name.setter
    def file_name(self, value: str) -> None:
        if not self.file_path and value:
            self.file_path = value

    @property
    def duration(self) -> Optional[float]:
        return self.duration_seconds

    @duration.setter
    def duration(self, value: Optional[float]) -> None:
        self.duration_seconds = value


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

    notes = synonym("note")

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

    access_token = synonym("access_token_encrypted")

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

    platform_post_id = synonym("external_post_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    publish_target_id: Mapped[int] = mapped_column(Integer, ForeignKey("publish_targets.id"), nullable=False)
    raw_post_id: Mapped[int] = mapped_column(Integer, ForeignKey("raw_posts.id"), nullable=False)
    external_post_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    published_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class SystemMetric(Base):
    __tablename__ = "system_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)

    def __init__(self, *args, **kwargs):
        if "cpu_percent" in kwargs and "metric_name" not in kwargs:
            kwargs["metric_name"] = "cpu_percent"
            kwargs["metric_value"] = float(kwargs.pop("cpu_percent") or 0.0)
            kwargs.pop("memory_rss_mb", None)
            kwargs.pop("threads_count", None)
        elif "memory_rss_mb" in kwargs and "metric_name" not in kwargs:
            kwargs["metric_name"] = "memory_rss_mb"
            kwargs["metric_value"] = float(kwargs.pop("memory_rss_mb") or 0.0)
            kwargs.pop("threads_count", None)
        super().__init__(*args, **kwargs)


class ActionLog(Base):
    __tablename__ = "action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    def __init__(self, *args, **kwargs):
        if "message" in kwargs and "details" not in kwargs:
            kwargs["details"] = kwargs.get("message")
        elif "details" in kwargs and "message" not in kwargs:
            kwargs["message"] = kwargs.get("details")
        super().__init__(*args, **kwargs)


class GeneratedVideo(Base):
    __tablename__ = "generated_videos"

    file_path = synonym("output_path")
    hook_title = synonym("title")
    mode = synonym("video_type")

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_post_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("raw_posts.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Bản tin")
    output_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    voice_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="ready")
    video_type: Mapped[str] = mapped_column(String(50), default="auto")
    script_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    raw_post: Mapped[Optional["RawPost"]] = relationship("RawPost", back_populates="generated_videos")


class VoiceProfile(Base):
    __tablename__ = "voice_profiles"



    name = synonym("speaker_name")

    created_by_user_id = synonym("created_by_id")

    ref_audio_path = synonym("reference_path")

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



    audio_path = synonym("output_path")

    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    raw_post_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    progress: Mapped[Optional[int]] = mapped_column(Integer, default=0)

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    voice_key: Mapped[str] = mapped_column(String(100), nullable=False)
    voice_label: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, default="Giọng đọc")
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
    audio_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, default="")
    talking_photo: Mapped[bool] = mapped_column(Boolean, default=True)
    layout: Mapped[str] = mapped_column(String(50), default="pip_bottom_right")
    engine: Mapped[str] = mapped_column(String(50), default="local")
    status: Mapped[str] = mapped_column(String(50), default="queued")
    output_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

# Aliases for backward compatibility
RawPostMedia = MediaItem
