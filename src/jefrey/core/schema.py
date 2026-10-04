"""Inicializacao do schema (extension + tabelas + indices HNSW)."""

from __future__ import annotations

from sqlalchemy import text

from src.jefrey.core.db import get_engine, Base as DbBase
from src.jefrey.core.models import Base as ModelsBase


def init_db() -> None:
    """Cria extension vector, tabelas e indices HNSW de similaridade coseno."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    ModelsBase.metadata.create_all(engine)
    DbBase.metadata.create_all(engine)  # Cria oauth_tokens e oauth2_clients (CIPHER-001)
    # ALTERs manuais comentados - as tabelas devem ser criadas via models.py metadata
    # P4: adiciona coluna expires_at na tabela approvals (ja existente desde P3). Idempotente.
    # with engine.begin() as conn:
    #     conn.execute(text("ALTER TABLE approvals ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ"))
    # P4-CRITICO R-01: audit_logs.user_id drift fix — DDIA cap6 migracao idempotente, Axiom #2 isolamento
    # with engine.begin() as conn:
    #     conn.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_id VARCHAR(128) NOT NULL DEFAULT 'system'"))
    #     conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs(user_id)"))


if __name__ == "__main__":
    init_db()
    print("Banco de dados Jefrey inicializado (PostgreSQL + pgvector).")
