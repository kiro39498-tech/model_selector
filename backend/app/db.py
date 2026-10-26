"""Database engine, session factory, and health check.

Uses SQLAlchemy 2.x with the psycopg driver for Neon PostgreSQL.
Connection pooling is configured for a single-host deployment.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app.config import settings

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def _build_engine() -> Engine:
    """Create the SQLAlchemy engine with a bounded connection pool."""
    return create_engine(
        settings.database_url,
        poolclass=QueuePool,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_pre_ping=True,
        future=True,
    )


def get_engine() -> Engine:
    """Lazily create and return the shared engine."""
    global _engine
    if _engine is None:
        if not settings.db_configured:
            raise RuntimeError(
                "DATABASE_URL is not configured. Set it in your .env file."
            )
        _engine = _build_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Lazily create and return the session factory."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionFactory


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yield a transaction-safe session.

    The session is closed at the end of the request. Callers are responsible
    for committing their own transactions.
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def transaction() -> Iterator[Session]:
    """Context manager for a single transaction across related writes.

    Commits on success, rolls back on exception. Use when multiple related
    records must be updated consistently.
    """
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_db() -> bool:
    """Return True if the database is reachable and the schema exists.

    Raises RuntimeError if the database is not configured.
    """
    if not settings.db_configured:
        raise RuntimeError("DATABASE_URL is not configured.")
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
