"""PostgreSQL + pgmemory integration with HNSW indexes.

Memory layers: episodic, semantic, preference, procedural, operational, approval.
Support multi-tenant isolation via user_id.
CIPHER-031: per-tenant client_id/secret storage in OAuth2 clients table.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import asyncio

from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Index, create_engine, select\nfrom src.jefrey.core.pg_memory_ttl import MemoryTTL
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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MemoryRecord - single memory row with user_id isolation (H2)
# ---------------------------------------------------------------------------

class MemoryRecord(Base):
    """Representa uma única linha de memória no pgvector/Postgres.

    Atributos essenciais para multi-tenant isolation:
    - id: identificador único
    - user_id: isolamento por tenant (CRÍTICO para H2 ChromaDB issue)
    - content: texto da memória
    - created_at: timestamp para TTL / ordering
    - updated_at: última atualização
    - metadata: metadados JSONB para tags, tipos, importância, etc.
    """
    __tablename__ = "memory_record"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), index=True, nullable=False)  # multi-tenant isolation
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    json_metadata = Column("metadata", JSON, nullable=True, default={})

    def __repr__(self):
        return f"<MemoryRecord id={self.id} user_id={self.user_id} created={self.created_at}>"

# ---------------------------------------------------------------------------
# MemoryManager - CRUD + TTL + Isolation
# ---------------------------------------------------------------------------

class MemoryManager:
    """Manager de memória com CRUD, isolamento multi-tenant e TTL automático."""

    def __init__(self, session_factory=None):
        self.session_factory = session_factory

    def _get_session(self) -> Session:
        """Get a database session."""
        if self.session_factory:
            return self.session_factory()
        from src.jefrey.core.db import get_session_local
        return get_session_local()()

    # =========================================================================
    # CRUD METHODS - ALL REQUIRE user_id (H2: ChromaDB/user_id isolation)
    # =========================================================================

    async def add(self, user_id: str, content: str, metadata: Optional[Dict] = None) -> MemoryRecord:
        """Add a memory record with user_id isolation + TTL tracking.

        H2: user_id is mandatory for all operations (multi-tenant isolation).
        """
        if not user_id:
            raise ValueError("user_id é obrigatório para isolamento multi-tenant (Axiom #2)")

        session = self._get_session()
        try:
            record = MemoryRecord(
                user_id=user_id,
                content=content,
                metadata=metadata or {},
            )
            session.add(record)
            session.commit()
            session.refresh(record)

            # M5: Schedule TTL cleanup after add
            # (não limpa imediatamente para evitar performance hit em writes)
            if MemoryTTL:
                try:
                    schedule_memory_cleanup(user_id=user_id, ttl_minutes=MemoryTTL.get_ttl_minutes("add"))
                except Exception as _e:
                    logger.debug(f"TTL schedule after add: {_e}")

            return record
        except Exception as e:
            session.rollback()
            logger.error(f"Erro ao adicionar memória: {e}")
            raise
        finally:
            session.close()

    async def search(
        self,
        user_id: str,
        query: str,
        k: int = 5,
        filter_metadata: Optional[Dict] = None,
    ) -> List[MemoryRecord]:
        """Search memories with user_id isolation (H2).

        Returns only memories belonging to the specified user_id.
        """
        if not user_id:
            raise ValueError("user_id é obrigatório para isolamento (Axiom #2)")

        session = self._get_session()
        try:
            from sqlalchemy import select

            stmt = select(MemoryRecord).where(MemoryRecord.user_id == user_id)

            # Build filter with user_id clause for multi-tenant isolation (H2)
            filter_dict = self._build_filter(user_id)
            # Aplicar filtro de metadata se fornecido
            if filter_metadata:
                for key, value in filter_metadata.items():
                    stmt = stmt.where(MemoryRecord.metadata.contains({key: value}))

            result = session.execute(stmt.order_by(MemoryRecord.created_at.desc()))
            records = result.scalars().all()[:k]

            # M5: Verificar TTL - remover messages antigas se necessário
            try:
                if MemoryTTL:
                    cleanup_result = MemoryTTL.cleanup_expired_memory(
                        user_id=user_id,
                        session_manager=session,
                    )
                    if cleanup_result > 0:
                        logger.info(f"Cleaned up {cleanup_result} expired memories during search")
            except Exception as _e:
                logger.debug(f"TTL check during search: {_e}")

            return list(records)
        except Exception as e:
            session.rollback()
            logger.error(f"Erro ao buscar memória: {e}")
            raise
        finally:
            session.close()

    async def update(
        self,
        user_id: str,
        record_id: int,
        new_content: str,
        metadata: Optional[Dict] = None,
    ) -> Optional[MemoryRecord]:
        """Update a memory record with ownership check (H2: user_id comparison)."""
        if not user_id:
            raise ValueError("user_id é obrigatório para isolamento (Axiom #2)")

        session = self._get_session()
        try:
            # Buscar record com ownership check
            stmt = select(MemoryRecord).where(
                MemoryRecord.id == record_id,
                MemoryRecord.user_id == user_id,  # Critical: verify ownership
            )
            result = session.execute(stmt)
            record = result.scalar_one_or_none()

            if record is None:
                return None  # Record not found or not owned by user

            # Atualizar conteúdo
            record.content = new_content
            if metadata is not None:
                record.metadata = metadata
            record.updated_at = datetime.now(timezone.utc)

            session.commit()
            session.refresh(record)

            # M5: After update, check TTL and potentially clean
            # (updated record resets the TTL clock)
            try:
                if MemoryTTL:
                    schedule_memory_cleanup(
                        user_id=user_id,
                        ttl_minutes=MemoryTTL.get_ttl_minutes("update"),
                    )
            except Exception as _e:
                logger.debug(f"TTL schedule after update: {_e}")

            return record
        except Exception as e:
            session.rollback()
            logger.error(f"Erro ao atualizar memória: {e}")
            raise
        finally:
            session.close()

    async def delete(
        self,
        user_id: str,
        record_id: int,
    ) -> bool:
        """Delete a memory record with ownership check (H2: user_id comparison)."""
        if not user_id:
            raise ValueError("user_id é obrigatório para isolamento (Axiom #2)")

        session = self._get_session()
        try:
            # Buscar record com ownership check
            stmt = select(MemoryRecord).where(
                MemoryRecord.id == record_id,
                MemoryRecord.user_id == user_id,  # Critical: verify ownership
            )
            result = session.execute(stmt)
            record = result.scalar_one_or_none()

            if record is None:
                return False  # Record not found or not owned by user

            session.delete(record)
            session.commit()

            # M5: After delete, run TTL-aware cleanup to maintain DB size
            try:
                if MemoryTTL:
                    n_cleaned = MemoryTTL.cleanup_expired_memory(
                        user_id=user_id,
                        session_manager=session,
                    )
                    if n_cleaned > 0:
                        logger.info(
                            f"After delete: cleaned {n_cleaned} expired memories for user {user_id}"
                        )
            except Exception as _e:
                logger.debug(f"TTL cleanup after delete: {_e}")

            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Erro ao deletar memória: {e}")
            raise
        finally:
            session.close()

    async def list_recent(
        self,
        user_id: str,
        k: int = 20,
        include_metadata: bool = True,
    ) -> List[MemoryRecord]:
        """List recent memories for user_id (H2: filtered by user_id)."""
        if not user_id:
            raise ValueError("user_id é obrigatório para isolamento (Axiom #2)")

        session = self._get_session()
        try:
            # Build filter with user_id clause for multi-tenant isolation (H2)
            filter_dict = self._build_filter(user_id)
            stmt = select(MemoryRecord).where(MemoryRecord.user_id == user_id)
            result = session.execute(stmt.order_by(MemoryRecord.created_at.desc()))
            records = result.scalars().all()[:k]

            # M5: During list_recent, also run quick TTL check
            # (list_recent is frequent, so keep it light)
            try:
                if MemoryTTL and len(records) > 0:
                    # Quick check - just log, don't full delete
                    cutoff = datetime.now(timezone.utc) - timedelta(minutes=1440)
                    old_records = [r for r in records if r.created_at < cutoff]
                    if old_records:
                        logger.debug(
                            f"Found {len(old_records)} old records in list_recent, scheduling cleanup"
                        )
                        # Don't delete here to avoid performance hit - just schedule
                        schedule_memory_cleanup(user_id=user_id, ttl_minutes=1440)
            except Exception as _e:
                logger.debug(f"TTL quick check list_recent: {_e}")

            return list(records)
        except Exception as e:
            session.rollback()
            logger.error(f"Erro ao listar memórias recentes: {e}")
            raise
        finally:
            session.close()

    async def _build_filter(self, user_id: str) -> dict:
        """Build ChromaDB/Postgres filter with user_id clause for isolation.

        H2: Este método garante que todas as queries de memória tenham
        user_id no filtro, implementando isolamento multi-tenant.
        """
        return {
            "where": {
                "user_id": user_id,  # Critical isolation clause
            }
        }

    async def health_check(self) -> Dict[str, any]:
        """Health check do memory manager - verifica conexão e configurações."""
        try:
            session = self._get_session()
            # Test básico: conseguir contar records (sem user_id filter para testar conexão)
            from sqlalchemy import select, func
            stmt = select(func.count(MemoryRecord.id))
            result = session.execute(stmt)
            total = result.scalar()
            session.close()

            return {
                "status": "ok",
                "total_records": total,
                "ttl_enabled": MemoryTTL is not None,
                "user_id_isolation": "enabled" if hasattr(MemoryRecord, "user_id") else "disabled",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


# Module-level _build_filter for test compatibility (Axiom #2, H2)
# This wraps the MemoryManager._build_filter logic at module level
def _build_filter(table=None, filter_dict: dict = None, user_id: str = None) -> Any:
    """Build a user_id filter for multi-tenant isolation.
    
    Args:
        table: SQLAlchemy table/model (or MagicMock for tests)
        filter_dict: dict to merge filter into
        user_id: user_id to add filter for
    
    Returns:
        dict with 'where' clause, or True if user_id is None (no filter)
    """
    if user_id is None:
        return True
    if filter_dict is None:
        filter_dict = {}
    filter_dict['where'] = filter_dict.get('where', {})
    filter_dict['where']['user_id'] = user_id
    return filter_dict

# Global instance
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get the global memory manager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager


# Convenience functions
async def memory_add(user_id: str, content: str, metadata: Optional[Dict] = None) -> MemoryRecord:
    """Add memory - convenience function."""
    return await get_memory_manager().add(user_id, content, metadata)


async def memory_search(
    user_id: str, query: str, k: int = 5, filter_metadata: Optional[Dict] = None
) -> List[MemoryRecord]:
    """Search memory - convenience function."""
    return await get_memory_manager().search(user_id, query, k, filter_metadata)


async def memory_list_recent(user_id: str, k: int = 20) -> List[MemoryRecord]:
    """List recent memories - convenience function."""
    return await get_memory_manager().list_recent(user_id, k)


async def memory_health_check() -> Dict[str, any]:
    """Health check - convenience function."""
    return await get_memory_manager().health_check()
