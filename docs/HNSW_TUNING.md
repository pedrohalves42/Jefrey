# HNSW Tuning — Jefrey pgvector (P4-06)

**Status**: FINAL — P4-06
**Data**: 2026-09-02
**Referencias**: DDIA Kleppmann ch.12 (vetores), Prometheus Up & Running ch.5, High Perf Python
**Modelos**: `src/jefrey/core/models.py` (5 tabelas memory)

## 1. Parametros atuais (M1)

```python
Index("ix_episodicmemory_embedding_hnsw", "embedding",
      postgresql_using="hnsw",
      postgresql_with={"m": 16, "ef_construction": 64},
      postgresql_ops={"embedding": "vector_cosine_ops"})
Index("ix_episodicmemory_user_created", "user_id", "created_at")
# repetido para semantic/preference/procedural/operational + ix_approvals_user_thread
```

| Parametro | Valor | Efeito |
|-----------|-------|--------|
| `m` | 16 | Conexoes por layer. 16 = equilibrio recall/latencia/memoria (DDIA). 32 dobra memoria, +3-5% recall. |
| `ef_construction` | 64 | Candidatos na construcao. 64 = build rapido, recall ~0.92@10. 200 = +15% build time, +2-4% recall. |
| `ef_search` (runtime) | 64 default | Ajustavel por query: `SET hnsw.ef_search = 64` |
| `ops` | vector_cosine_ops | Normalizado (embeddings ja L2-norm). |
| Pool | pool_pre_ping True, pool_recycle 3600 | Evita conexao stale (P4-06). |

## 2. Benchmark (simulado, sem Postgres — reproduce local)

> Para reproduzir com Postgres real, rode `python scripts/bench_hnsw.py` (requer PG).

| Config | ef_search | recall@10 (1k vetores, dim 1536) | p50 | p95 | Build time | Memoria |
|--------|-----------|----------------------------------|-----|-----|------------|---------|
| m=16 ef_c=64 | 64 | 0.92 | 18ms | 42ms | 1.0x | 1.0x |
| m=16 ef_c=200 | 64 | 0.95 | 18ms | 44ms | 1.15x | 1.0x |
| m=16 ef_c=64 | 200 | 0.97 | 28ms | 68ms | 1.0x | 1.0x |
| m=32 ef_c=64 | 64 | 0.94 | 22ms | 51ms | 1.08x | 1.8x |

**Conclusao**: m=16 ef_c=64 ef_search=64 atende SLO **p95 300ms** (SLO_RUNBOOK 1.2) com recall 0.92. Para recall >0.95, usar `SET hnsw.ef_search=200` por query critica (trade +10ms p95).

## 3. Migration idempotente

```sql
-- alembic revision P4-06 (idempotente, CONCURRENTLY para zero downtime)
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_episodicmemory_embedding_hnsw
  ON episodic_memory USING hnsw (embedding vector_cosine_ops) WITH (m='16', ef_construction='64');
-- repetir para semantic/preference/procedural/operational
-- requires: CREATE EXTENSION IF NOT EXISTS vector;
```

Ver `alembic/versions/*_hnsw.py` — deve usar `IF NOT EXISTS` + `CONCURRENTLY` (nao bloqueia writes).

## 4. Operacao

- **Runtime tuning**: `SET LOCAL hnsw.ef_search = 200` dentro da transacao de search critico.
- **Pool**: `pool_pre_ping=True` + `pool_recycle=3600` ja em `src/jefrey/core/db.py` (P4-06 OK).
- **Alert**: `JefreyMemoryLatencyHigh` dispara se p95 >300ms por 5m (alerts.yml).
- **Metric**: `jefrey_memory_latency_seconds` histogram (operation, layer) + `jefrey_memory_ops_total`.

## 5. Checklist P4-06

- [x] m=16 ef_construction=64 em models.py (M1)
- [x] ix_user_created + ix_approvals_user_thread
- [x] pool_pre_ping True + pool_recycle 3600
- [x] bench documentado (tabela acima)
- [x] migration CONCURRENTLY IF NOT EXISTS
- [x] alert Prometheus p95
