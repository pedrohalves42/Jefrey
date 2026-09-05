"""Migration de segurança: adiciona user_id em todas as tabelas de memória e approvals.

Rodar ANTES do primeiro startup em produção:
    python scripts/security_migration_user_id.py

Opção A (produção): DEFAULT 'system' preserva dados existentes.
"""
from __future__ import annotations

import sys
import os

# Garante que o diretório raiz do projeto está no path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text
from src.jefrey.core.db import get_engine

TABLES = [
    "episodic_memory",
    "semantic_memory",
    "preference_memory",
    "procedural_memory",
    "operational_memory",
    "approvals",
    "audit_logs",
]

def run_migration() -> bool:
    engine = get_engine()
    ok = True

    print("=" * 60)
    print("  JEFREY — Migration de Segurança: user_id")
    print("  Opção A: DEFAULT 'system' (preserva dados existentes)")
    print("=" * 60)
    print()

    with engine.connect() as conn:
        for table in TABLES:
            # 1. Adiciona coluna user_id
            sql_add = text(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "
                f"user_id VARCHAR(128) NOT NULL DEFAULT 'system'"
            )
            try:
                conn.execute(sql_add)
                print(f"  ✅ {table}.user_id — coluna adicionada (DEFAULT 'system')")
            except Exception as e:
                print(f"  ❌ {table}.user_id — ERRO ao adicionar coluna: {e}")
                ok = False
                continue

            # 2. Cria índice
            sql_idx = text(
                f"CREATE INDEX IF NOT EXISTS ix_{table}_user_id ON {table} (user_id)"
            )
            try:
                conn.execute(sql_idx)
                print(f"  ✅ ix_{table}_user_id — índice criado")
            except Exception as e:
                print(f"  ❌ ix_{table}_user_id — ERRO ao criar índice: {e}")
                ok = False

        # 3. Commit
        conn.commit()

    # 4. Verificação pós-migration
    print()
    print("─" * 60)
    print("  Verificação pós-migration:")
    print("─" * 60)

    with engine.connect() as conn:
        for table in TABLES:
            sql_check = text(
                f"SELECT column_name, column_default "
                f"FROM information_schema.columns "
                f"WHERE table_name = '{table}' AND column_name = 'user_id'"
            )
            result = conn.execute(sql_check).fetchone()
            if result:
                print(f"  ✅ {table}.user_id — default={result[1]}")
            else:
                print(f"  ❌ {table}.user_id — NÃO ENCONTRADO!")
                ok = False

    print()
    if ok:
        print("  🎉 Migration concluída com sucesso! Todas as 7 tabelas protegidas.")
    else:
        print("  ⚠️  Migration com erros — revise os logs acima.")
    print()
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if run_migration() else 1)
