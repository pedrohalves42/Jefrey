"""Conexão SQLAlchemy + pool para PostgreSQL/pgvector."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.jefrey.core.config import get_settings

_engine = None
_SessionLocal = None


def get_engine():
    """Engine singleton (criado sob demanda)."""
    global _engine
    if _engine is None:
        s = get_settings().database
        _engine = create_engine(
            s.dsn,
            pool_pre_ping=True,
            pool_size=s.pool_size,
            max_overflow=s.max_overflow,
            echo=s.echo,
            future=True,
        )
    return _engine


def get_session_local():
    """SessionMaker singleton."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _SessionLocal


@contextmanager
def get_db() -> Iterator[Session]:
    """Context manager de sessão com commit/rollback automático."""
    session = get_session_local()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
