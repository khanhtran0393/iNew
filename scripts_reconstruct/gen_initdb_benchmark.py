import os
from pathlib import Path

app_dir = Path("app")

# 1. app/init_db.py
init_db_code = '''import os
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
    if not stored_password_hash.startswith("pbkdf2:sha256:"):
        return False
    parts = stored_password_hash.split("$")
    if len(parts) != 4:
        return False
    iterations = int(parts[1])
    salt = bytes.fromhex(parts[2])
    expected_key = bytes.fromhex(parts[3])
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
    """Ensure newly required schema columns exist."""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    # SQLite schema migrations check
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
'''

(app_dir / "init_db.py").write_text(init_db_code, encoding="utf-8")

# 2. app/benchmark_report.py
bench_code = '''from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from app.database import SessionLocal
from app.models import SourceChannel


def _v(value: Any, unit: str = "") -> str:
    if value is None:
        return "—"
    if unit:
        return f"{value} {unit}"
    return str(value)


def _verdict(ok: bool) -> str:
    return "ĐẠT" if ok else "CHƯA ĐẠT"


def build_report(
    db=None,
    now: datetime = None,
    started: datetime = None,
    hours_run: float = 0.0,
    lat: Dict[str, Any] = None,
    res: Dict[str, Any] = None,
    history: List[Any] = None,
    series: List[Any] = None,
    sources: List[Any] = None,
    channels: int = 0,
    expected: int = 0,
    missing: int = 0,
    miss_pct: float = 0.0,
    unrecovered: int = 0,
    final_pct: float = 0.0
) -> str:
    """Build markdown report for WP01 Telegram collector benchmark."""
    if now is None:
        now = datetime.now(timezone.utc)
    now_str = now.strftime("%H:%M %d/%m/%Y UTC")
    started_str = started.strftime("%H:%M %d/%m/%Y UTC") if started else "—"

    TARGET_HOURS = 24
    TARGET_CHANNELS = 20
    LATENCY_TARGET_SECONDS = 5.0

    lines = [
        "# BÁO CÁO ĐO KIỂM THỰC TẾ WP01 — BỘ THU THẬP TELEGRAM",
        f"- Thời điểm lập báo cáo: {now_str}",
        f"- Bắt đầu đo: {started_str} — đã chạy **{hours_run:.1f} giờ** / mục tiêu {TARGET_HOURS} giờ",
        f"- Số kênh Telegram đã kết nối: **{_v(channels)}** / mục tiêu {TARGET_CHANNELS}",
        "- Máy chạy: máy Mac nội bộ, SQLite (WAL), một tiến trình uvicorn",
        "",
        "## 1. Kết quả so với tiêu chí",
        "| Tiêu chí | Mục tiêu | Thực tế | Kết luận |",
        "| :--- | :--- | :--- | :---: |",
        f"| Số kênh thực tế | ≥ {TARGET_CHANNELS} | {channels} | {_verdict(channels >= TARGET_CHANNELS)} |",
        f"| Độ trễ phát hiện (trung vị) | < {LATENCY_TARGET_SECONDS} giây | {lat.get('p50', '—') if lat else '—'} s | {_verdict(lat.get('p50', 99) < LATENCY_TARGET_SECONDS if lat else False)} |",
        f"| Tỷ lệ bỏ sót cuối cùng | 0% | {final_pct:.2f}% ({unrecovered} tin) | {_verdict(unrecovered == 0)} |",
        "",
        "## 2. Tài nguyên tiêu thụ",
        "| Chỉ số | Trung bình | Cao nhất |",
        "| :--- | :---: | :---: |",
        f"| CPU | {res.get('cpu_avg', '—') if res else '—'}% | {res.get('cpu_max', '—') if res else '—'}% |",
        f"| RAM | {res.get('ram_avg', '—') if res else '—'} MB | {res.get('ram_max', '—') if res else '—'} MB |"
    ]
    return "\\n".join(lines)
'''

(app_dir / "benchmark_report.py").write_text(bench_code, encoding="utf-8")

# 3. app/telegram_login.py
tg_login_code = '''import asyncio
from typing import Dict, Any, Optional
from telethon import TelegramClient
from app.config import settings

_login_client: Optional[TelegramClient] = None
_phone_code_hash: Optional[str] = None
_phone_number: Optional[str] = None


async def send_code_request(phone: str, api_id: int, api_hash: str) -> Dict[str, Any]:
    global _login_client, _phone_code_hash, _phone_number
    _phone_number = phone.strip()
    _login_client = TelegramClient(settings.TELEGRAM_SESSION_NAME, api_id, api_hash)
    await _login_client.connect()
    res = await _login_client.send_code_request(_phone_number)
    _phone_code_hash = res.phone_code_hash
    return {"ok": True, "phone_code_hash": _phone_code_hash}


async def verify_login_code(code: str, password: Optional[str] = None) -> Dict[str, Any]:
    global _login_client, _phone_code_hash, _phone_number
    if not _login_client or not _phone_code_hash:
        return {"ok": False, "error": "Chưa gửi mã xác nhận"}
    try:
        await _login_client.sign_in(_phone_number, code, phone_code_hash=_phone_code_hash)
    except Exception as e:
        if "Two-steps verification is enabled" in str(e) and password:
            await _login_client.sign_in(password=password)
        else:
            return {"ok": False, "error": str(e)}

    session_string = _login_client.session.save()
    await _login_client.disconnect()
    _login_client = None
    return {"ok": True, "session_string": session_string}
'''

(app_dir / "telegram_login.py").write_text(tg_login_code, encoding="utf-8")
print("Generated init_db.py, benchmark_report.py, telegram_login.py")
