"""Modelos SQLAlchemy — 6 camadas de memória + aprovações HITL (P4).

Camadas:
  - Working      -> Redis (ver redis_memory.py) — NÃO persistida no SQL
  - Episodic      -> episodic_memory
  - Semantic      -> semantic_memory
  - Preference    -> preference_memory
  - Procedural    -> procedural_memory
  - Operational   -> operational_memory
"""
from __future__ import annotations

import uuid

from sqlalchemy import Column, String, Text, DateTime, func, Float
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase

from pgvector.sqlalchemy import Vector

from src.jefrey.core.config import get_settings

EMBED_DIM = get_settings().memory.long_term.embedding_dim


class Base(DeclarativeBase):
    pass


class _MemoryMixin:
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(EMBED_DIM), nullable=False)
    title = Column(String(512), nullable=True)
    source = Column(String(128), nullable=True, default="user")
    tags = Column(ARRAY(String), nullable=False, default=lambda: [])
    metadata_json = Column(JSONB, nullable=False, default=lambda: {})
    importance = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class EpisodicMemory(_MemoryMixin, Base):
    __tablename__ = "episodic_memory"


class SemanticMemory(_MemoryMixin, Base):
    __tablename__ = "semantic_memory"


class PreferenceMemory(_MemoryMixin, Base):
    __tablename__ = "preference_memory"


class ProceduralMemory(_MemoryMixin, Base):
    __tablename__ = "procedural_memory"


class OperationalMemory(_MemoryMixin, Base):
    __tablename__ = "operational_memory"


class Approval(Base):
    """Solicitações de aprovação Human-in-the-Loop (P4)."""

    __tablename__ = "approvals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(String(128), nullable=False, index=True)
    tool_name = Column(String(256), nullable=False)
    arguments_json = Column(JSONB, nullable=False, default=lambda: {})
    risk_level = Column(String(32), nullable=False, default="medium")
    status = Column(String(32), nullable=False, default="pending")  # pending|approved|rejected|expired
    reason = Column(Text, nullable=True)
    created_by = Column(String(128), nullable=True)
    decided_by = Column(String(128), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


MEMORY_TABLES = {
    "episodic": EpisodicMemory,
    "semantic": SemanticMemory,
    "preference": PreferenceMemory,
    "procedural": ProceduralMemory,
    "operational": OperationalMemory,
}


def memory_table(layer: str):
    if layer not in MEMORY_TABLES:
        raise ValueError(
            f"Camada de memória inválida: {layer}. Use uma de {list(MEMORY_TABLES)}"
        )
    return MEMORY_TABLES[layer]
