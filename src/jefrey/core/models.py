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

from sqlalchemy import Column, String, Text, DateTime, func, Float, Index
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase

from pgvector.sqlalchemy import Vector

from src.jefrey.core.config import get_settings

EMBED_DIM = get_settings().memory.long_term.embedding_dim


class Base(DeclarativeBase):
    pass


class _MemoryMixin:
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(128), nullable=False, server_default="'system'", index=True)
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

    __table_args__ = (
        Index("ix_episodicmemory_embedding_hnsw", "embedding", postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("ix_episodicmemory_user_created", "user_id", "created_at"),
    )


class SemanticMemory(_MemoryMixin, Base):
    __tablename__ = "semantic_memory"

    __table_args__ = (
        Index("ix_semanticmemory_embedding_hnsw", "embedding", postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("ix_semanticmemory_user_created", "user_id", "created_at"),
    )


class PreferenceMemory(_MemoryMixin, Base):
    __tablename__ = "preference_memory"

    __table_args__ = (
        Index("ix_preferencememory_embedding_hnsw", "embedding", postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("ix_preferencememory_user_created", "user_id", "created_at"),
    )


class ProceduralMemory(_MemoryMixin, Base):
    __tablename__ = "procedural_memory"

    __table_args__ = (
        Index("ix_proceduralmemory_embedding_hnsw", "embedding", postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("ix_proceduralmemory_user_created", "user_id", "created_at"),
    )


class OperationalMemory(_MemoryMixin, Base):
    __tablename__ = "operational_memory"

    __table_args__ = (
        Index("ix_operationalmemory_embedding_hnsw", "embedding", postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("ix_operationalmemory_user_created", "user_id", "created_at"),
    )


class Approval(Base):
    """Solicitações de aprovação Human-in-the-Loop (P4)."""

    __tablename__ = "approvals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(128), nullable=False, server_default="'system'", index=True)
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
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)  # P4: prazo do approval (approval_ttl)

    __table_args__ = (
        Index("ix_approvals_user_thread", "user_id", "thread_id"),
        Index("ix_approvals_expires", "expires_at"),
    )


class AuditLog(Base):
    """Log de auditoria forense (P4, CIPHER-010) — substitui docker logs."""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ts = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    user_id = Column(String(128), nullable=False, server_default="'system'", index=True)
    thread_id = Column(String(128), nullable=False, index=True)
    tool_name = Column(String(256), nullable=False)
    actor_role = Column(String(32), nullable=False, default="user")
    risk = Column(String(32), nullable=False, default="unknown")
    decision = Column(String(32), nullable=False)
    reason = Column(Text, nullable=True)
    approval_id = Column(String(64), nullable=True, index=True)
    approval_decision = Column(String(32), nullable=True)
    source = Column(String(32), nullable=False, default="agent")
    detail_json = Column(JSONB, nullable=False, default=lambda: {})


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
