"""Inicialização do schema (extension + tabelas + índices HNSW)."""
from __future__ import annotations

from sqlalchemy import text

from src.jefrey.core.db import get_engine
from src.jefrey.core.models import Base, MEMORY_TABLES


def init_db() -> None:
    """Cria extension vector, tabelas e índices HNSW de similaridade coseno."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    # P4: adiciona coluna expires_at na tabela approvals (já existente desde P3). Idempotente.
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE approvals ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ"))
    with engine.begin() as conn:
        # Garante que metadata_json seja JSONB (idempotente; no-op se já for jsonb).
        # Necessário porque filtros usam os operadores @> / ->> da JSONB.
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
    with engine.begin() as conn:
        for name in MEMORY_TABLES:
            conn.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS {name}_embedding_idx "
                    f"ON {name}_memory USING hnsw (embedding vector_cosine_ops)"
                )
            )


if __name__ == "__main__":
    init_db()
    print("✅ Banco de dados Jefrey inicializado (PostgreSQL + pgvector).")
