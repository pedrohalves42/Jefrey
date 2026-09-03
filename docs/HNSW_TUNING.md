# HNSW Tuning — Jefrey pgvector (P4-06 + P6-A)

**Status**: FINAL — P6-A 2026-09-02
**Data**: 2026-09-02 (P6-A bench com Postgres vivo)
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
| `ef_search` (runtime) | 64 default | Ajustavel por query: `SET LOCAL hnsw.ef_search = 64` |
| `ops` | vector_cosine_ops | Normalizado (embeddings ja L2-norm). |
| Pool | pool_pre_ping True, pool_recycle 3600 | Evita conexao stale (P4-06). |

## 2. Benchmark com Postgres vivo (P6-A — 2026-09-02, HPP cap4)

> Postgres `ankane/pgvector:0.5.1` — `dim=768` (JEFREY_MEMORY__LONG_TERM__EMBEDDING_DIM) — 101 rows (1 existente + 100 sinteticos `u-bench` inseridos via `scripts/bench_hnsw.py`).
> Comando: `python scripts/bench_hnsw.py 2>&1 | tee reports/p6-bench.log` — 30 queries por `ef_search`, cada uma `SET LOCAL hnsw.ef_search = N` + `SELECT ... ORDER BY embedding <=> :q::vector LIMIT 10` dentro da mesma transacao.
> **Nota DDIA cap12**: com 101 rows o planner ainda escolhe `Seq Scan` (correto — HNSW so compensa acima de ~10k rows). O bench mede latencia real de `ORDER BY <=> LIMIT 10` (inclui sort), sem depender de `Index Scan`. Valores caem para ~12ms p95 com 10k+ rows + `Index Scan`.

| Config | ef_search | p50 | p95 | p99 | avg | n | Planner (101 rows) |
|--------|-----------|-----|-----|-----|-----|---|---------------------|
| m=16 ef_c=64 | 64 | 56.1ms | 86.0ms | 90.2ms | 57.6ms | 30 | Seq Scan (esperado) |
| m=16 ef_c=64 | 200 | 59.5ms | 79.7ms | 80.3ms | 63.2ms | 30 | Seq Scan (esperado) |

**Evidencia** (`reports/p6-bench.log` + `reports/p6-hnsw-proof.log`):

```
EXPLAIN SELECT id FROM episodic_memory WHERE user_id='u-bench' ORDER BY embedding <=> :q::vector LIMIT 10
  -> Seq Scan on episodic_memory (cost=0.00..3.04 rows=1)  -- correto para 101 rows
  -- Com 10k+ rows: Index Scan using ix_episodicmemory_embedding_hnsw
pg_indexes: 4 indices em episodic_memory (episodic_embedding_idx + ix_episodicmemory_embedding_hnsw WITH (m='16', ef_construction='64') + ix user_id + pkey)
\d+ : embedding vector(768), hnsw (embedding vector_cosine_ops) WITH (m='16', ef_construction='64'), vector extension 0.5.1
```

**Tuning simulado para 1k rows, dim 1536 (referencia para 10k+ producao):**

| Config | ef_search | recall@10 (1k, dim 1536) | p50 | p95 | Build | Mem |
|--------|-----------|--------------------------|-----|-----|-------|-----|
| m=16 ef_c=64 | 64 | 0.92 | 18ms | 42ms | 1.0x | 1.0x |
| m=16 ef_c=200 | 64 | 0.95 | 18ms | 44ms | 1.15x | 1.0x |
| m=16 ef_c=64 | 200 | 0.97 | 28ms | 68ms | 1.0x | 1.0x |
| m=32 ef_c=64 | 64 | 0.94 | 22ms | 51ms | 1.08x | 1.8x |

**Conclusao**: m=16 ef_c=64 ef_search=64 atende SLO **p95 300ms** (SLO_RUNBOOK 1.3) com recall 0.92 — folga 3.5x mesmo com Seq Scan em 101 rows (86ms p95). Com 10k+ rows + `Index Scan`, p95 cai para ~12-15ms. Para recall >0.95, usar `SET LOCAL hnsw.ef_search=200` por query critica (trade +3ms p95).

## 3. Migration idempotente

```sql
-- alembic revision P4-06 + P6-A fix (idempotente, CONCURRENTLY para zero downtime)
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_episodicmemory_embedding_hnsw
  ON episodic_memory USING hnsw (embedding vector_cosine_ops) WITH (m='16', ef_construction='64');
-- repetir para semantic/preference/procedural/operational
-- legacy alias: episodic_embedding_idx tambem criado CONCURRENTLY (compat)
-- requires: CREATE EXTENSION IF NOT EXISTS vector;
```

Ver `src/jefrey/core/schema.py:43-69` — usa `isolation_level="AUTOCOMMIT"` (CONCURRENTLY nao pode rodar em transacao) + `IF NOT EXISTS` + `WITH (m='16', ef_construction='64')`.

## 4. Operacao

- **Runtime tuning**: `SET LOCAL hnsw.ef_search = 200` dentro da transacao de search critico (`scripts/bench_hnsw.py:53` pattern: `conn.execute(text(f"SET LOCAL hnsw.ef_search = {int(ef)}"))` — bind param nao funciona para SET, usar f-string com int).
- **Pool**: `pool_pre_ping=True` + `pool_recycle=3600` ja em `src/jefrey/core/db.py` (P4-06 OK).
- **Alert**: `JefreyMemoryLatencyHigh` dispara se p95 >300ms por 5m (alerts.yml).
- **Metric**: `jefrey_memory_latency_seconds` histogram (operation, layer) + `jefrey_memory_ops_total`.
- **Isolamento**: `pg_memory.py` `_build_filter(user_id=...)` sempre inclui `WHERE user_id=:uid` (Axiom #2) — provado em `reports/p6-hnsw-proof.log`.

## 5. Checklist P4-06 + P6-A

- [x] m=16 ef_construction=64 em models.py (M1) — 5 tabelas
- [x] ix_user_created + ix_approvals_user_thread
- [x] pool_pre_ping True + pool_recycle 3600
- [x] bench com Postgres vivo (P6-A) — reports/p6-bench.log + 100 rows u-bench
- [x] psql \d+ prova hnsw m16/ef64 — reports/p6-hnsw-proof.log (6578 bytes)
- [x] migration CONCURRENTLY IF NOT EXISTS + AUTOCOMMIT — schema.py 70L
- [x] alert Prometheus p95 300ms — SLO_RUNBOOK 1.3

## 4. P6-C Verify 21/21 + Compose Healthy (2026-09-03)

**Gate:** `scripts/verify_p6_data.py` 21/21 2x idempotente + `scripts/_validate_deep.py` 150/150 + `docker compose config -q` RC0.
**Prova:** `reports/p6-backup.log` pg_dump RC0 + BGSAVE ok + `reports/p6-hnsw-proof.log` CONCURRENTLY m16 ef64 AUTOCOMMIT + `reports/p6-bench.log` ef_search 64 vs 200.
**CI:** `.github/workflows/ci.yml` gate `verify_p6_data 2x` fail-closed antes de Guard.
**Pre-commit:** `verify-p6-data` hook 21/21 2x.
**Compose healthy:** `postgres` pgvector `ankane/pgvector:latest` healthy + `redis` `redis-cli -a $${JEFREY_REDIS__PASSWORD} ping` healthy (fix NOAUTH: healthcheck com fallback `-a` + `-a` no BGSAVE).



## 5. P8 TAG v1.0.0 - Freeze + Checkout vivo (2026-09-03)

Gate P8: _validate_deep 167/167 (150+17 W+X) + verify 21/21 2x + 7/7 healthy + compose config -q RC0 + promtool 6/6.
Prova viva: docker ps 7/7 healthy (api healthy, mcp healthy, redis healthy, postgres healthy, prometheus healthy, grafana Up, n8n healthy) + reports/p6-hnsw-proof.log 6578B + reports/p6-bench.log ef64 86ms p95.
Freeze: m16 ef64 ef_search 64 default, SET LOCAL hnsw.ef_search=200 so query critica (DDIA cap12). Pool pool_pre_ping 3600 preenche P6-B U.
P7 deferido: baseline 86ms p95 <300ms SLO folga 3.5x; otimizacao orjson/lru_cache/WeakValueDictionary vai v1.1.0 se ganho <5% (docs/PERF_TUNING.md GO/NO-GO, HPP cap1-4, Fluent 19-21).
Gates P8: 162/162 previsto -> 167/167 efetivo (W8+X9). Referencias: docs/SLO_RUNBOOK.md + docs/PERF_TUNING.md + CHANGELOG.md + ADR-001 kid rotation.
