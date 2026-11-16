"""Database engine and session management."""

import os
import contextlib
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

if settings.DATABASE_URL.startswith("sqlite"):
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    connect_args = {"check_same_thread": False, "timeout": 60}
    engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, connection_record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=60000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()
else:
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextlib.contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for standalone database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
