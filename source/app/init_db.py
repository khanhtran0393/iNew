"""Database schema initialization, default roles and admin creation."""

import os
import json
import hashlib
from datetime import datetime, timezone
from app.database import engine, Base, SessionLocal
from app.models import Role, User, RoleSlug
from app.config import settings


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return f"pbkdf2:sha256:100000${salt.hex()}${key.hex()}"


def verify_password(stored_password_hash: str, password: str) -> bool:
    if not stored_password_hash or not password:
        return False
    try:
        parts = stored_password_hash.split("$")
        if len(parts) != 3 or not parts[0].startswith("pbkdf2:sha256:"):
            return False
        iterations = int(parts[0].split(":")[2])
        salt = bytes.fromhex(parts[1])
        key = bytes.fromhex(parts[2])
        test_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hashlib.sha256(test_key).digest() == hashlib.sha256(key).digest()
    except Exception:
        return False


def init_db():
    """Create all tables and seed default roles and admin account."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Default Roles
        default_roles = [
            (RoleSlug.ADMIN.value, ["*"]),
            (RoleSlug.LEAD.value, ["edit", "review", "approve", "publish", "sources", "topics"]),
            (RoleSlug.EDITOR.value, ["edit", "review", "publish"]),
            (RoleSlug.MONITOR.value, ["view", "monitor"]),
            (RoleSlug.VIEWER.value, ["view"]),
        ]
        roles_by_slug = {}
        for slug, perms in default_roles:
            role = db.query(Role).filter(Role.slug == slug).first()
            if not role:
                role = Role(
                    id=slug,
                    slug=slug,
                    permissions_json=json.dumps(perms),
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None)
                )
                db.add(role)
                db.commit()
                db.refresh(role)
            roles_by_slug[slug] = role

        # Admin user
        admin = db.query(User).filter(User.username == settings.ADMIN_USERNAME).first()
        if not admin:
            admin = User(
                username=settings.ADMIN_USERNAME,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                full_name=settings.ADMIN_FULL_NAME,
                role_id=roles_by_slug[RoleSlug.ADMIN.value].id,
                is_active=True,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None)
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()
