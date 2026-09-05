"""Inicializacao do schema (extension + tabelas + indices HNSW)."""

from __future__ import annotations

from sqlalchemy import text

from src.jefrey.core.db import get_engine, Base as DbBase
from src.jefrey.core.models import Base as ModelsBase, MEMORY_TABLES


def init_db() -> None:
    """Cria extension vector, tabelas e indices HNSW de similaridade coseno."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    ModelsBase.metadata.create_all(engine)
    DbBase.metadata.create_all(engine)
    # P4: adiciona coluna expires_at na tabela approvals (ja existente desde P3). Idempotente.
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE approvals ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ"))
    # P4-CRITICO R-01: audit_logs.user_id drift fix — DDIA cap6 migracao idempotente, Axiom #2 isolamento
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_id VARCHAR(128) NOT NULL DEFAULT 'system'"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs(user_id)"))
    with engine.begin() as conn:
        # Garante que metadata_json seja JSONB (idempotente; no-op se ja for jsonb).
        # Necessario porque filtros usam os operadores @> / ->> da JSONB.
        for name in MEMORY_TABLES:
            conn.execute(
                text(
                    f"""
                    DO $$
                    BEGIN
                      IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = '{name}_memory'
                          AND column_name = 'metadata_json'
                          AND data_type = 'json'
                      ) THEN
                        ALTER TABLE {name}_memory ALTER COLUMN metadata_json TYPE jsonb USING metadata_json::jsonb;
                      END IF;
                    END $$;
                    """
                )
            )
    # P6-A: HNSW indices CONCURRENTLY IF NOT EXISTS — idempotente, zero downtime (DDIA cap12).
    # CREATE INDEX CONCURRENTLY nao pode rodar dentro de transacao -> usa AUTOCOMMIT.
    # Index spec deve casar com models.py: m=16 ef_construction=64 vector_cosine_ops.
    with engine.connect() as conn:
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        for name in MEMORY_TABLES:
            idx = f"ix_{name}memory_embedding_hnsw"
            conn.execute(
                text(
                    f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {idx} "
                    f"ON {name}_memory USING hnsw (embedding vector_cosine_ops) "
                    f"WITH (m='16', ef_construction='64')"
                )
            )
        # Compat: mantem alias antigo {name}_embedding_idx se ainda usado por queries legado
        for name in MEMORY_TABLES:
            legacy = f"{name}_embedding_idx"
            conn.execute(
                text(
                    f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {legacy} "
                    f"ON {name}_memory USING hnsw (embedding vector_cosine_ops) "
                    f"WITH (m='16', ef_construction='64')"
                )
            )


if __name__ == "__main__":
    init_db()
    print("Banco de dados Jefrey inicializado (PostgreSQL + pgvector).")
