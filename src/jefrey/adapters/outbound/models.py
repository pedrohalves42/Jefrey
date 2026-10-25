"""P5 — Database Models (SQLAlchemy).

Defines base models and mixins for multi-tenant isolation.
Critical: All tables MUST have user_id for tenant isolation (Axiom #2, SEC-001).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, func, Text, Index, UUID
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class _MemoryMixin:
    """Mixin para isolamento multi-tenant via user_id (SEC-001, Axiom #2).

    Todas as tabelas de memória DEVEM incluir user_id como coluna indexada
    e não-nula para garantir isolamento entre tenants.
    """
    user_id = Column(
        String(100),
        index=True,
        nullable=False,
        doc="Tenant isolation - mandatory for all memory operations"
    )


class MemoryRecord(Base, _MemoryMixin):
    """Registro de memória de longo prazo com isolamento por user_id."""
    __tablename__ = "memory_records"

    id = Column(String(36), primary_key=True)
    content = Column(String, nullable=False)
    metadata_json = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    ttl_minutes = Column(String(10), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<MemoryRecord id={self.id} user_id={self.user_id} created={self.created_at}>"




# =============================================================================
# 6-Layer Memory Tables (P1: episodic, semantic, preference, procedural, operational, approval)
# Each layer has its own table with user_id isolation (SEC-001, Axiom #2)
# =============================================================================

class EpisodicMemoryRecord(Base, _MemoryMixin):
    """Episodic memory - conversational history and interactions."""
    __tablename__ = "memory_episodic"
    id = Column(String(36), primary_key=True)
    content = Column(String, nullable=False)
    metadata_json = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    ttl_minutes = Column(String(10), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

class SemanticMemoryRecord(Base, _MemoryMixin):
    """Semantic memory - knowledge base and facts."""
    __tablename__ = "memory_semantic"
    id = Column(String(36), primary_key=True)
    content = Column(String, nullable=False)
    metadata_json = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    ttl_minutes = Column(String(10), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

class PreferenceMemoryRecord(Base, _MemoryMixin):
    """Preference memory - user preferences and constraints."""
    __tablename__ = "memory_preference"
    id = Column(String(36), primary_key=True)
    content = Column(String, nullable=False)
    metadata_json = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    ttl_minutes = Column(String(10), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

class ProceduralMemoryRecord(Base, _MemoryMixin):
    """Procedural memory - tool execution workflows and recipes."""
    __tablename__ = "memory_procedural"
    id = Column(String(36), primary_key=True)
    content = Column(String, nullable=False)
    metadata_json = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    ttl_minutes = Column(String(10), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

class OperationalMemoryRecord(Base, _MemoryMixin):
    """Operational memory - system execution state and background tasks."""
    __tablename__ = "memory_operational"
    id = Column(String(36), primary_key=True)
    content = Column(String, nullable=False)
    metadata_json = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    ttl_minutes = Column(String(10), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

# ApprovalMemoryRecord removido - usando Approval table específica em db.py para HITL
# Mantido aqui apenas para compatibilidade, deve ser removido após migração

# =============================================================================
# OAuth Tokens - Multi-tenant OAuth2 tokens for Google integrations
# =============================================================================
# OAuthToken moved to db.py to avoid duplication - imported below
from src.jefrey.core.db import OAuthToken

# =============================================================================
# memory_table() - dispatches to layer-specific tables
# =============================================================================

def memory_table(layer: str):
    """Dispatch to layer-specific memory table class.

    Args:
        layer: One of 'episodic', 'semantic', 'preference', 'procedural', 'operational'

    Returns:
        SQLAlchemy model class for the specified layer

    Raises:
        ValueError: If layer is not one of the 5 supported layers
    """
    layer = layer.lower().strip()
    tables = {
        'episodic': EpisodicMemoryRecord,
        'semantic': SemanticMemoryRecord,
        'preference': PreferenceMemoryRecord,
        'procedural': ProceduralMemoryRecord,
        'operational': OperationalMemoryRecord,
    }
    if layer not in tables:
        raise ValueError(f"Invalid memory layer: {layer}. Supported: {list(tables.keys())}")
    return tables[layer]

# Export
__all__ = ["Base", "_MemoryMixin", "MemoryRecord", "EpisodicMemoryRecord", "SemanticMemoryRecord", "PreferenceMemoryRecord", "ProceduralMemoryRecord", "OperationalMemoryRecord", "memory_table"]

# Import OAuthToken and Approval from db.py for backward compatibility
from src.jefrey.core.db import OAuthToken, Approval


# =============================================================================
# CIPHER-305: tabela audit_logs. core/audit.py importava models.AuditLog, que nao existia:
# 100% dos eventos de auditoria caiam no arquivo de fallback e o Postgres nunca tinha rastro.
# =============================================================================
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(String(100), nullable=False, index=True)
    thread_id = Column(String(255), nullable=False, index=True)
    tool_name = Column(String(128), nullable=False)
    actor_role = Column(String(32), nullable=False)
    risk = Column(String(16), nullable=False)
    decision = Column(String(32), nullable=False)
    reason = Column(Text, nullable=True)
    approval_id = Column(String(64), nullable=True)
    approval_decision = Column(String(32), nullable=True)
    source = Column(String(32), nullable=False, default="agent")
    detail_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    def __repr__(self):
        return f"<AuditLog {self.tool_name} {self.decision} user={self.user_id}>"
