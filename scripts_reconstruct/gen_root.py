import os
from pathlib import Path

app_dir = Path("app")
app_dir.mkdir(exist_ok=True)

# 1. app/__init__.py
(app_dir / "__init__.py").write_text('"""iNew News Aggregation and Multi-Platform Publishing System."""\n__version__ = "1.0.0"\n', encoding="utf-8")

# 2. app/_build_info.py
(app_dir / "_build_info.py").write_text('''"""Build information and default licensing keys."""
VERSION = "1.0.0"
PUBLIC_KEY = "VnOm9l4HxzfkSKJAvRhrveS-W6HmP759iP9jcPW1wEM"
LICENSE_SERVER_URL = ""
ENFORCE = True
''', encoding="utf-8")

# 3. app/database.py
(app_dir / "database.py").write_text('''import os
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

# Ensure data directory exists
if settings.DATABASE_URL.startswith("sqlite"):
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    connect_args = {"check_same_thread": False, "timeout": 60}
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args=connect_args,
        pool_pre_ping=True
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
else:
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for standalone background worker sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
''', encoding="utf-8")

print("Generated __init__.py, _build_info.py, database.py")
