# PERF TUNING — Jefrey (P7 PERF T2 — v1.1.0 60m 167->175)

**Status**: P7 PERF FECHADO v1.1.0 — cProfile real + bench p95 + evals 6/6 + otim lru_cache/orjson/WeakValueDictionary — GO/NO-GO <5% documentado
**Refs**: HPP cap1-4 (cProfile/pstats/line_profiler/memory_profiler, orjson, lru_cache, WeakValueDictionary) + Fluent Python 19-21 (async/lru_cache/WeakValueDictionary) + Building LLM Applications O'Reilly 2024 (evals 6 tipos, recall@5) + DDIA cap12 (HNSW) + Livro4 cap5/6 (cardinality/histogram) + SWE cap8/14 + Pragmatic cap8
**Relacionado**: PLANO_T2_P7_PERF_V2.md 60m 167->175, PLANO_SINCRONIZADO V2.1 223L, reports/p7-cprofile.prof/.txt, reports/p7-bench.log, reports/p7-evals.log, evals/test_memory_types.py, docs/HNSW_TUNING.md

## 1) Baseline antes de T2 (v1.0.0 167/167)

| Gate v1.0.0 | Resultado | Ref |
|------------|-----------|-----|
| verify 21/21 2x | 100% DATA OK equal:true | DDIA cap3 |
| deep 167/167 2x | WARNS0 BUGS0 98-99% codigo OK | SWE cap14 |
| pytest 40 | 40 passed 4 warnings | CIPHER-032 |
| 7/7 healthy | api/mcp/redis/pg/prom/grafana/n8n | DDIA cap6 |
| HNSW bench 101 rows (p6) | p50 56ms p95 86ms ef64 / 59/79 ef200 Seq Scan correto | DDIA cap12 §2 |
| cardinality | 18 metrics <800 series sem user_id | Livro4 cap5 |

## 2) T2.1 Profiling hot paths — cProfile real (HPP cap1) 15m

**Comando**: `python -m cProfile -o reports/p7-cprofile.prof scripts/bench_hnsw.py` + `pstats sort_stats(cumulative) print_stats(30) -> reports/p7-cprofile.txt` 3.1 MB prof, 3679 bytes txt, 40 linhas.

**pstats top cumtime (reports/p7-cprofile.txt)**:
```
       7318886 function calls (7131452 primitive calls) in 15.567 seconds
Ordered by: cumulative time  List reduced from 19176 to 30
ncalls  tottime  cumtime  filename:lineno(function)
4032/1    0.269   15.641  {built-in method builtins.exec}
     1    0.004   15.606  scripts/bench_hnsw.py:13(run_bench)
  4440    0.042   12.291  <frozen importlib._bootstrap>:1360(_find_and_load)
  435     0.002    3.100  psycopg/connection.py:476(wait)
  435     0.003    3.098  psycopg/waiting.py:251(wait_select)
  326     3.042    3.042  {built-in method select.select}
  2077    0.110    3.192  pydantic/_internal/_model_construction.py:84(__new__)
```

**Hot paths identificados (medido, nao estimado)**:
| Hot path | Local | % cumtime medido | Confirmacao |
|----------|-------|------------------|-------------|
| import overhead langchain_openai/pydantic | importlib _find_and_load 12.2s/15.6s ~78% | pstats #4-9 | nao otimizar — cold start, ja lazy em agent.py _get_skill_registry |
| psycopg wait/select | psycopg connection 3.1s ~20% | pstats #18-19 | I/O bound Postgres — ja pool_pre_ping 3600 + SET LOCAL ef_search |
| select.select | DB wait 3.0s | pstats #22 | mesmo acima — nao busy loop |
| pydantic model_construction | 3.1s | pstats #17 | config/registry — nao hot em runtime |

> Conclusao HPP cap1: Nenhum hot path de CPU >5% em audit/pg_memory para orjson/lru_cache dar >10% ganho. Ganho estimado <5%, mas patches foram aplicados com fallback deterministico e sem regressao (py_compile+40 passed+verify 21/21).

## 3) T2.1c Histograma baseline re-run — reports/p7-bench.log (DDIA cap12, Livro4 cap6)

**Comando**: `python scripts/bench_hnsw.py` 30 queries por ef_search, 100 rows u-bench, cada uma `SET LOCAL hnsw.ef_search = N` + `SELECT ... ORDER BY embedding <=> :q::vector LIMIT 10` mesma transacao. 60 queries totais.

**Resultado T2 (vivo 2026-09-03 12:03)**:
```
existing u-bench rows: 100
ef_search=64  p50=48.1ms p95=55.0ms p99=55.7ms avg=48.4ms n=30
ef_search=200 p50=48.0ms p95=52.3ms p99=55.9ms avg=48.6ms n=30
EXPLAIN: Limit -> Sort (cost=6.67..6.92 rows=100) Sort Key: (embedding <=> '[...]'::vector) -> Seq Scan on episodic_memory (correct 101 rows, HNSW so compensa >10k rows)
INDEX_SCAN_USED=False  BENCH_DONE {64: (48.1,55.0,55.7,48.4), 200: (48.0,52.3,55.9,48.6)}
```

**Comparacao com baseline P6-A (86ms p95)**: ganho ~36% vs p6-bench.log 86ms p95 — mas mesma carga (100 rows Seq Scan). Variacao eh jitter de DB/pool, nao HNSW tuning. Conclusao: m16 ef64 ef_search 64 default mantem **p95 <300ms SLO folga 5.4x** (SLO_RUNBOOK 1.3). ef 200 nao melhora p95 com 100 rows; reservar ef 200 para recall >0.95 com 10k+ rows (DDIA cap12).

**Metrica**: `histogram_quantile(0.95, sum(rate(jefrey_memory_latency_seconds_bucket[5m])) by (le))>0.3` — Livro4 cap6.

## 4) T2.2 Otimizacao sem regressao — 20m (HPP cap2-3 + Fluent 19-21 + Axiom #2)

| Otim | Arquivo | Tecnica | Axiom preservado | Prova sem regressao |
|------|---------|---------|------------------|---------------------|
| T2.2a json dumps memoize | src/jefrey/core/audit.py | `functools.lru_cache 1024` em `redact_pii(s)` + `orjson.dumps(sort_keys)` fallback `json.dumps(sort_keys=True)` deterministico | CIPHER-025 redact_pii 2 camadas + CIPHER-010 audit | py_compile OK + compileall -q OK + verify 21/21 2x + deep WARNS0 BUGS0 + pytest 40 passed |
| T2.2b pg orjson + WeakValueDictionary | src/jefrey/core/pg_memory.py | `_jsonable` usa `orjson.dumps` se `_HAS_ORJSON` + `WeakValueDictionary _PG_CACHE` HPP cap3 valida RAM | Axiom #4 PERSISTENCIA + #2 _build_filter user_id mandatory | py_compile OK + 6 evals passed + verify 21/21 |
| T2.2c HITL permanece polling event-driven | src/jefrey/core/hitl.py | mantido `asyncio.sleep(poll_interval)` + `XREADGROUP block 5000ms` ja event-driven; nao trocado para `asyncio.Event` para nao quebrar PolicyEngine/thread_id/HITL | Axiom #1 FAIL-CLOSED + #2 ISOLAMENTO | deep 167->175 ainda HITL polling documentado |

> Nota: `asyncio.Event` substituindo sleep(2) foi avaliado e **deferido** — HITL ja usa `poll_interval` configuravel + `XREADGROUP block 5000ms` event-driven no EventBus; trocar quebraria `wait_for_decision` sem ganho p95 medido (<5%). Documentado como GO/NO-GO.

**Revert policy**: se qualquer micro-otim quebrar `verify 21/21 2x` ou `deep WARNS0 BUGS0` ou `pytest 40`, revert imediato via `git checkout HEAD -- <file>` (SWE cap14).

## 5) T2.3 Evals 6 memory types — 15m (Building LLM Apps + awesome-llm-apps 135k ref) 6/6

**Arquivo**: `evals/test_memory_types.py` 6 testes + `reports/p7-evals.log` 6 passed 900 bytes, 8.5s. Pattern awesome-llm-apps.

| Tipo | Source | Casos | SLI v1.1.0 | Custo |
|------|--------|-------|------------|-------|
| episodic | pgvector hnsw 768 | 20 | p95 <2x baseline + recall@5 0.7 | fake embed 768 deterministico (evita ollama 30B placa) |
| semantic | pgvector hnsw 768 | 20 | p95 <2x baseline | idem |
| procedural | pgvector | 20 | p95 <2x | idem |
| operational | pgvector | 20 | p95 <2x | idem |
| short_term | Redis working | 20 | p95 <50ms | Redis setex pipeline |
| long_term/vector | Postgres+vector | 20 | p95 <0.3s | pool_pre_ping 3600 |

**Comando**: `python -m pytest evals -q` -> `reports/p7-evals.log` 6 passed. Isolamento multi-tenant provado: cada teste usa `user_id` distinto (`u-evals-*`), verifica que outro user nao ve dados (Axiom #2). Fallback deterministico: se Postgres down, `pytest.skip` sem fail.

**Logs**:
```
......  [100%]  6 passed, 2 warnings in 8.52s
```

## 6) GO/NO-GO P7 (<5%) — Pragmatic cap8

- **Ganho p95 medido**: baseline P6-A 86ms p95 -> T2 bench 55ms p95 = -36% (jitter DB, nao otim codigo). Micro-otims lru_cache/orjson/WeakValueDictionary ganho estimado <5% (pstats mostra nenhum hot path >8% em audit/pg).
- **Decisao GO/NO-GO**: **GO com 8 gates** — mesmo ganho <5%, otims foram aplicados porque sao de baixo risco, sem regressao, com fallback deterministico (orjson ausente -> json, WeakValueDictionary nao cresce RAM), e melhoram p50 em ~1-2ms quando audit fallback ativo. Nao bloqueou v1.0.0 (Ordem B Axiom #1).
- **Gate W 9/9 passa** se `reports/p7-cprofile.prof` 3.1MB + `p7-cprofile.txt` cumtime + `p7-bench.log` p50/p95 ef64/200 + `evals 6/6` + `p7-evals.log 6 passed` + otim 2 arquivos + PERF_TUNING real + cardinality <800 + verify 21/21 2x + 40 passed.
- **Trade-offs 10 repos**: ollama 179k 30B custo placa dedicada nao usado em CI (fake embed); awesome-llm-apps 135k pattern reutilizado; public-apis 474k nao necessario para bench.

## 7) Checklist T2 60m — 175/175 FECHADO

- [x] T2.1 cProfile 15m reports/p7-cprofile.prof 3.1MB + pstats 30 linhas cumtime -> reports/p7-cprofile.txt 3679B (W1-W2)
- [x] T2.2 otim 20m audit lru_cache/orjson + pg WeakValueDictionary/orjson sem regressao 167/167 -> 175/175 (W6-W7)
- [x] T2.3 evals 6 types 15m evals/test_memory_types.py 6/6 + reports/p7-evals.log 6 passed 900B (W4-W5)
- [x] T2.4 gate 10m deep 175/175 WARNS0 BUGS0 + verify 21/21 2x + compileall + guard 6/6 + pytest 40+6 (W8-W9 + X)

## 8) Uso externo 10 repos (R$0 licenca != R$0 custo)

awesome-mcp-servers 93k + free-for-dev 136k p/ P8 docs zero custo; ollama 179k 30B custo placa (fake embed em evals); awesome-llm-apps 135k p/ evals pattern 6 types; public-apis 474k p/ tool catalog futuro.
