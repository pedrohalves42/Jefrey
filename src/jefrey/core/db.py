"""Conexao SQLAlchemy + pool para PostgreSQL/pgvector.
Also defines OAuth2 client table for CIPHER-031 multi-tenant isolation.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Index
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base

from src.jefrey.core.config import get_settings

Base = declarative_base()

# OAuth2 clients table model (CIPHER-031: per-tenant client_id/secret storage)
class Oauth2Client(Base):
    """OAuth2 client registration for per-tenant isolation.

    Stores client_id, client_secret (hashed), allowed scopes, and tenant_id.
    Used by auth_middleware.py for client validation and token introspection.
    """
    __tablename__ = "oauth2_clients"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String(255), unique=True, nullable=False, index=True)
    client_secret_hash = Column(String(255), nullable=False)
    tenant_id = Column(String(100), nullable=False, index=True)
    allowed_scopes = Column(JSON, nullable=True, default=[])
    is_confidential = Column(Integer, nullable=False, default=0)  # 0=False, 1=True
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_oauth2_client_id", "client_id"),
        Index("ix_oauth2_tenant_id", "tenant_id"),
    )


# Engine singleton (thread-safe, criado sob demanda)
_engine = None
_SessionLocal = None
_engine_lock = threading.Lock()
_session_lock = threading.Lock()

def get_engine():
    """Engine singleton (thread-safe, criado sob demanda)."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                s = get_settings().database
                _engine = create_engine(
                    s.dsn,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    pool_size=s.pool_size,
                    max_overflow=s.max_overflow,
                    echo=s.echo,
                    future=True,
                )
    return _engine

def get_session_local():
    """SessionMaker singleton (thread-safe)."""
    global _SessionLocal
    if _SessionLocal is None:
        with _session_lock:
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
    """Context manager de sessao com commit/rollback automatico."""
    session = get_session_local()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# Table creation / migration helper (CIPHER-031)
def create_oauth2_tables() -> None:
    """Create oauth2_clients table if not exists (idempotent migration).

    Uses Base.metadata.create_all to be idempotent - safe to run multiple times.
    Should be called during app startup or Docker entrypoint.
    """
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger_info = __import__("logging").getLogger(__name__)
    logger_info.info("OAuth2 tables created/verified (oauth2_clients)")