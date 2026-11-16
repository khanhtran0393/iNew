import os
import hmac
import hashlib
from typing import List, Dict, Any
from sqlalchemy import inspect, text
from app.database import Base, engine, SessionLocal
from app.config import settings
from app.models import (
    Role, User, Topic, AppSetting, RoleSlug,
    SourceChannel, TopicSource, RawPost, RawPostStatus, WorkflowStatus,
    EditorialGroup, MediaItem, MediaType
)


def hash_password(password: str) -> str:
    """Hash password with PBKDF2-HMAC-SHA256 (100,000 iterations)."""
    salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        100000
    ).hex()
    return f"pbkdf2:sha256:100000${salt}${key}"


def verify_password(stored_password_hash: str, password: str) -> bool:
    """Verify password against stored PBKDF2 hash."""
    if not stored_password_hash or not stored_password_hash.startswith("pbkdf2:sha256:"):
        return False
    parts = stored_password_hash.split("$")
    if len(parts) == 3:
        iter_str = parts[0].split(":")[-1]
        iterations = int(iter_str)
        salt = bytes.fromhex(parts[1])
        expected_key = bytes.fromhex(parts[2])
    elif len(parts) == 4:
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_key = bytes.fromhex(parts[3])
    else:
        return False
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations
    )
    return hmac.compare_digest(key, expected_key)


def seed_database(db) -> None:
    """Seed initial system roles, default admin user, default topics and settings."""
    roles_data = [
        {
            "name": "Quản Trị Viên (Admin)",
            "slug": RoleSlug.ADMIN.value,
            "permissions_json": '["*"]',
            "description": "Toàn quyền quản trị hệ thống, người dùng và bản quyền"
        },
        {
            "name": "Biên Tập Viên (Editor)",
            "slug": RoleSlug.EDITOR.value,
            "permissions_json": '["posts:view", "posts:claim", "posts:edit", "posts:verify", "posts:review", "ai:use", "sources:view", "media:download"]',
            "description": "Biên tập tin bài, duyệt và chỉnh sửa đa phương tiện"
        },
        {
            "name": "Trưởng Ban (Duyệt bài, giao việc)",
            "slug": RoleSlug.LEAD.value,
            "permissions_json": '["posts:*", "posts:approve", "posts:assign", "ai:use", "audit:view"]',
            "description": "Phân công bài viết, duyệt tin và giám sát quy trình"
        },
        {
            "name": "Nhân Viên Theo Dõi (Lọc tin)",
            "slug": RoleSlug.MONITOR.value,
            "permissions_json": '["posts:view", "posts:skip", "sources:view"]',
            "description": "Theo dõi luồng tin thô và gắn nhãn nhanh"
        },
        {
            "name": "Người Xem (Viewer)",
            "slug": RoleSlug.VIEWER.value,
            "permissions_json": '["posts:view"]',
            "description": "Chỉ xem danh sách bài viết"
        }
    ]

    role_map = {}
    for r in roles_data:
        existing = db.query(Role).filter_by(slug=r["slug"]).first()
        if not existing:
            new_role = Role(**r)
            db.add(new_role)
            db.flush()
            role_map[r["slug"]] = new_role
        else:
            role_map[r["slug"]] = existing

    # Seed Admin User
    admin_user = db.query(User).filter_by(username=settings.ADMIN_USERNAME).first()
    if not admin_user:
        admin_role = role_map.get(RoleSlug.ADMIN.value)
        new_admin = User(
            username=settings.ADMIN_USERNAME,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            full_name=settings.ADMIN_FULL_NAME,
            role_id=admin_role.id,
            is_active=True
        )
        db.add(new_admin)

    # Seed Default Topics
    default_topics = [
        {"name": "Thời sự Trong nước", "slug": "thoi-su-trong-nuoc", "description": "Tin tức thời sự chính trị, kinh tế, xã hội Việt Nam"},
        {"name": "Thế giới", "slug": "the-gioi", "description": "Tin tức quốc tế, địa chính trị thế giới"},
        {"name": "Kinh tế & Thị trường", "slug": "kinh-te", "description": "Tài chính, chứng khoán, bất động sản và doanh nghiệp"},
        {"name": "Công nghệ & AI", "slug": "cong-nghe", "description": "Trí tuệ nhân tạo, thiết bị di động và số hóa"}
    ]
    for t in default_topics:
        if not db.query(Topic).filter_by(slug=t["slug"]).first():
            db.add(Topic(**t))

    # Seed Default Settings
    default_settings = {
        "app_name": settings.APP_NAME,
        "allow_lan": "true" if settings.ALLOW_LAN else "false",
        "ai_enabled": "true" if settings.AI_ENABLED else "false",
        "ai_model": settings.AI_MODEL,
        "tts_voice": settings.TTS_VOICE,
        "dedup_threshold": str(settings.DEDUP_FUZZY_THRESHOLD),
    }
    for k, v in default_settings.items():
        if not db.query(AppSetting).filter_by(key=k).first():
            db.add(AppSetting(key=k, value=v))

    db.commit()


def encrypt_plaintext_secrets(db) -> None:
    """Ensure any plaintext secrets in DB are encrypted with application key."""
    # Placeholder for runtime encryption verification
    pass


def ensure_schema_columns(engine) -> None:
    """Ensure newly required schema columns exist in SQLite database."""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    migrations = {
        "source_channels": [
            ("username", "VARCHAR(255)"),
            ("priority", "VARCHAR(50) DEFAULT 'NORMAL'"),
            ("last_fetched_at", "DATETIME")
        ],
        "users": [
            ("telegram_user_id", "VARCHAR(100)")
        ],
        "raw_posts": [
            ("normalized_text", "TEXT"),
            ("published_at_source", "DATETIME"),
            ("ingest_method", "VARCHAR(50)"),
            ("editorial_notes", "TEXT"),
            ("published_url", "VARCHAR(500)"),
            ("is_source_edited", "BOOLEAN DEFAULT 0"),
            ("deleted_at", "DATETIME")
        ],
        "media_items": [
            ("remote_url", "VARCHAR(500)")
        ],
        "action_logs": [
            ("entity_type", "VARCHAR(100)"),
            ("entity_id", "INTEGER"),
            ("message", "TEXT")
        ],
        "generated_videos": [
            ("error_message", "TEXT")
        ],
        "publish_logs": [
            ("published_url", "VARCHAR(500)")
        ]
    }

    with engine.connect() as conn:
        for table, cols in migrations.items():
            if table in existing_tables:
                col_names = [c["name"] for c in inspector.get_columns(table)]
                for col_name, col_type in cols:
                    if col_name not in col_names:
                        try:
                            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
                            conn.commit()
                        except Exception:
                            pass


def seed_default_rss_sources(db) -> None:
    """Seed initial reputable Vietnamese news RSS feeds."""
    rss_list = [
        ("VnExpress - Thời sự", "https://vnexpress.net/rss/thoi-su.rss"),
        ("VnExpress - Thế giới", "https://vnexpress.net/rss/the-gioi.rss"),
        ("Tuổi Trẻ - Thời sự", "https://tuoitre.vn/rss/thoi-su.rss"),
        ("Thanh Niên - Thời sự", "https://thanhnien.vn/rss/thoi-su.rss"),
        ("Dân Trí - Xã hội", "https://dantri.com.vn/rss/xa-hoi.rss")
    ]
    for title, url in rss_list:
        if not db.query(SourceChannel).filter_by(rss_url=url).first():
            sc = SourceChannel(
                title=title,
                source_type="rss",
                rss_url=url,
                url=url,
                is_active=True
            )
            db.add(sc)
    db.commit()


def init_db() -> None:
    """Full database setup routine."""
    Base.metadata.create_all(bind=engine)
    ensure_schema_columns(engine)
    db = SessionLocal()
    try:
        seed_database(db)
        seed_default_rss_sources(db)
        encrypt_plaintext_secrets(db)
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("Database initialization completed.")
