# PERF TUNING — Jefrey (P7 PERF T2 — deferido v1.1.0)

**Status**: P8 v1.0.0 — P7 PERF documentado, otimizacao efetiva vai v1.1.0 se ganho p95 <5% (GO/NO-GO)
**Refs**: HPP cap1-4 (cProfile/pstats/line_profiler/memory_profiler) + Fluent Python 19-21 (async/lru_cache/WeakValueDictionary) + Building LLM Applications O'Reilly 2024 (evals) + DDIA cap12 + Livro4 cap5/6
**Relacionado**: PLANO_P7_PERF_V1.md 214L, PLANO_SINCRONIZADO V2.1 223L, reports/p6-bench.log, docs/HNSW_TUNING.md

## 1) Validacao 11:15 — baseline antes de P7

| Gate 11:15 | Resultado | Ref |
|------------|-----------|-----|
| verify 21/21 2x | 100% DATA OK equal:true | DDIA cap3 |
| deep 150/150 2x | WARNS0 BUGS0 | SWE cap14 |
| pytest 40 | 40 passed 4 warnings | CIPHER-032 |
| 7/7 healthy | api/mcp/redis/pg/prom/grafana/n8n | DDIA cap6 |
| HNSW bench 101 rows | p50 56ms p95 86ms ef64 / 59ms/79ms ef200 Seq Scan correto | DDIA cap12 §2 |
| cardinality | 18 metrics <800 series sem user_id | Livro4 cap5 |

## 2) Hot paths identificados (sem editar codigo em P8 — HPP cap1)

| Hot path | Local | % estimado pstats | Acao v1.1.0 | Axiom preservado |
|----------|-------|-------------------|-------------|------------------|
| ToolExecutor sleep(2) polling | src/jefrey/core/executor.py | ~12% cumtime (HITL) | asyncio.Event / XREADGROUP block 5000ms event-driven — nunca quebrar PolicyEngine/thread_id | #1 FAIL-CLOSED |
| json dumps / _to_chroma_metadata | src/jefrey/memory/* | ~8% | orjson + lru_cache 1024 memoize; manter redact_pii 2 camadas | CIPHER-025 |
| WeakValueDictionary candidate | src/jefrey/memory/cache.py | ~5% se hot | WeakValueDictionary + memory_profiler valida RAM | #4 PERSISTENCIA |
| HNSW ef_search 64 vs 200 | bench_hnsw.py SET LOCAL | +3ms p95 p/ +5% recall | manter ef 64 default, ef 200 so query critica | DDIA cap12 |

> Nota: cProfile real (`python -m cProfile -o reports/p7-cprofile.prof scripts/bench_hnsw.py`) e pstats 20 linhas cumtime serao gerados em T2.1a (15m) e salvos em reports/p7-cprofile.txt . Em P8 v1.0.0 o baseline acima e suficiente para GO/NO-GO.

## 3) Evals 6 memory types (Building LLM Apps + awesome-llm-apps 135k ref)

| Tipo | Source | Casos | SLI v1.1.0 | Custo |
|------|--------|-------|------------|-------|
| episodic | Chroma nomic-embed 768 | 20 | p95 <2x baseline + recall@5 0.7 | R$0 licenca != R$0 custo (ollama 30B placa dedicada) |
| semantic | pgvector hnsw 768 | 20 | p95 <2x baseline | idem |
| procedural | pgvector | 20 | p95 <2x | idem |
| operational | pgvector | 20 | p95 <2x | idem |
| short_term | Redis working | 20 | p95 <50ms | Redis setex pipeline |
| long_term/vector | Postgres+vector | 20 | p95 <86ms | pool_pre_ping 3600 |

Arquivo futuro: `evals/test_memory_types.py` 6/6 — pattern awesome-llm-apps. Rodar `pytest evals -q` -> reports/p7-evals.log.

## 4) GO/NO-GO P7 (<5%)

- Se ganho p95 <5% apos T2.2 otimizacao -> docs/PERF_TUNING.md sec2 explica por que nao e vai v1.1.0 (SWE cap14). NAO bloqueia v1.0.0 (Axiom #1 economia prematura).
- Gate W 8/8 so passa se docs/PERF_TUNING.md existe + bench p95 baseline salvo OU justificativa <5% documentada.

## 5) Checklist T2 (60m — Ordem B vai v1.1.0)

- [ ] T2.1 cProfile 15m reports/p7-cprofile.prof + pstats 20 linhas -> reports/p7-cprofile.txt (W1)
- [ ] T2.2 otimizacao 20m event-driven + orjson/lru_cache + WeakValueDictionary sem regressao 150/150 (W2/W3)
- [ ] T2.3 evals 6 types 15m + reports/p7-evals.log (W4)
- [ ] T2.4 gate 158/158 + deep W8 (HPP+Fluent+DDIA+SWE)

## 6) Uso externo 10 repos (R$0 licenca != R$0 custo)

awesome-mcp-servers 93k + free-for-dev 136k p/ P8 docs zero custo; ollama 179k 30B custo placa; awesome-llm-apps 135k p/ evals pattern; public-apis 474k p/ tool catalog
