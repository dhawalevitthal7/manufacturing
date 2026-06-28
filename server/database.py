"""Database engine, session factory, and SQLite concurrency helpers."""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)

SQLALCHEMY_DATABASE_URL = "sqlite:///./manufacturing_os.db"

# One writer at a time — API threads + background cascade share manufacturing_os.db.
_sqlite_write_lock = threading.Lock()

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 60},
    poolclass=NullPool,
    echo=False,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=60000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def ensure_wal_mode() -> None:
    try:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA busy_timeout=60000"))
            conn.commit()
            mode = conn.execute(text("PRAGMA journal_mode")).scalar()
            logger.info("SQLite journal_mode=%s", mode)
    except Exception as exc:
        logger.warning("Could not set WAL mode: %s", exc)


@contextmanager
def sqlite_write() -> Generator[None, None, None]:
    _sqlite_write_lock.acquire()
    try:
        yield
    finally:
        _sqlite_write_lock.release()


def _retry_op(fn, session, label: str, *, max_attempts: int = 10) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            with sqlite_write():
                fn()
            return
        except OperationalError as exc:
            try:
                session.rollback()
            except Exception:
                pass
            if "locked" not in str(exc).lower() or attempt == max_attempts:
                logger.error("SQLite %s failed after %s attempts: %s", label, attempt, exc)
                raise
            wait = min(0.25 * attempt, 2.0)
            logger.warning("SQLite %s locked (attempt %s/%s), retry in %.1fs", label, attempt, max_attempts, wait)
            time.sleep(wait)


def flush_with_retry(session) -> None:
    _retry_op(session.flush, session, "flush")


def commit_with_retry(session) -> None:
    _retry_op(session.commit, session, "commit")


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
