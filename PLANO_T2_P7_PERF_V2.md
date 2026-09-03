# PLANO T2 — P7 PERF v1.1.0 (Ordem B, deferido) — 60m — 167→175 — pos v1.0.0 f93578a

> **Base v1.0.0 validada:** 167/167 WARNS0 BUGS0 + 21/21 2x 100% DATA OK + 40 passed + 7/7 healthy (api/mcp/redis/postgres/prometheus/grafana Up/n8n healthy) + promtool 6/6 + grafana 8 panels by(le):2 + compose RC0 + guard 6/6 + compileall RC0
> **Objetivo:** PERF real sem quebrar nada (Axiom #1 FAIL-CLOSED, #2 ISOLAMENTO, #4 PERSISTENCIA, #6 LEAST PRIVILEGE + CIPHER 021/025/026/033 + DDIA cap12 + Livro4 cap5/6 + HPP cap1-4 + Fluent 19-21 + Building LLM Apps O'Reilly 2024 + SWE cap8/14 + Pragmatic)
> **GO/NO-GO:** ganho p95 <5% -> apenas docs/PERF_TUNING.md sec2 explica por que nao e fecha 175/175 com justificativa; NAO bloqueia v1.0.0 (ja tagueado). 175 so se ganho >=5% OU docs <5% existe.

## 0) Diagnostico pessimista — o que falta para 100% + 5%

| Gate v1.0.0 | Estado | O que falta para v1.1.0 (T2) | Gates |
|-------------|--------|-------------------------------|-------|
| docs/PERF_TUNING.md existe | 1 arquivo 3708B mas sem cProfile real | cProfile real + pstats 20 linhas + reports/p7-cprofile.prof/.txt | W1-W2 (migrar docs-only -> prova viva) |
| p95 baseline 86ms ef64 | so bench P6-A 101 rows | bench re-run dedicado reports/p7-bench.log p95 por tipo | W3 |
| evals 6 types | so tabela no PERF_TUNING | evals/test_memory_types.py 6/6 + reports/p7-evals.log | W4 |
| otimizacao | nao feita | 3 micro-otims com revert se regressao | W5-W7 |
| deep 167/167 | WARNS0 BUGS0 | deep 175/175 + verify 21/21 2x + 40 passed + 6/6 + compose RC0 | W8 |

TOTAL T2: 60m. Sem T2 v1.0.0 100% ja entregue. Com T2 v1.1.0 100%+5%.

## 1) Principios inegociaveis (nao quebrar v1.0.0)

**Axiom 6 FAIL-CLOSED:**
- FAIL-CLOSED deny/false/raise: nunca `return "allow"` em rate_limit; PolicyEngine UNKNOWN deny
- ISOLAMENTO user_id=None->guest + _build_filter mandatory + topic jefrey.events.{user_id}.{tool} + DLQ jefrey:dlq:{user_id} + _ns_thread_id — provado tests/test_p6_isolation 2/2
- SEM STUB EM PROD JEFREY_ENV dev/prod + validate_for_production() 8 envs ?required — valid_ stub so dev gated prod
- PERSISTENCIA REAL setex pipeline incr/expire + pool_pre_ping 3600 + TTLCache so dev + backup pg_dump/BGSAVE file-only idempotente (DDIA cap3)
- CRIPTO urlsafe_b64encode sem padding RS256+kid aud/iss/exp/kid/alg compare_digest sort_keys kid rotation v1->v2 dual-verify (ADR-001, CIPHER-033)
- LEAST PRIVILEGE overwrite=False :ro CORS explicit enumerated allow_credentials False pool_pre_ping 3600

**CIPHER:**
- 021 silent except nunca `except: pass` -> logger (guard GREP-3)
- 025 dual-write audit Postgres->data/audit_fallback.jsonl redact_pii 2 camadas
- 026 rate limiting pipeline incr/expire fail-closed
- 033 HMAC kid v1/v2 + EVENTBUS_KID_LEGACY_TOTAL labelnames=[] 1 serie global (Livro4 cap5 <800 series)
- 032 Skill Risk overwrite=False + load_skills() + RBAC guest/user/admin + HITL
- 035 Token Refresh httpx real + timeout + valid_ dev-only prod RuntimeError
- 031 JWKS urlsafe + RS256 + kid + alias jwsk com DeprecationWarning

**Livros T2 (ordem B — DEPOIS):**
- HPP cap1-4 (cProfile/pstats/line_profiler/memory_profiler, orjson, lru_cache, WeakValueDictionary)
- Fluent Python 19-21 (async, decorators, descriptors)
- Building LLM Applications O'Reilly 2024 (evals 6 tipos, recall@5 0.7, p95 <2x)
- DDIA cap12 (HNSW tuning m16 ef64 vs m32, ef_search 64 vs 200)
- Livro4 cap5 cardinality (nunca user_id) cap6 histogram_quantile by(le) cap10 alerting cap11 Grafana
- SWE cap8 Style cap14 Testing (py_compile + compileall + guard 6/6 + pytest 40)
- Pragmatic cap8 (CHANGELOG, PERF_TUNING justificativa <5%)

**Qualidade (SWE cap8 + Fluent + Pragmatic):** py_compile + compileall -q + guard_anti_patterns 6 greps + audit_pessimista + metrics_no_user_id + guard_grafana + verify 21/21 2x + deep 175/175 + promtool 6/6 + compose healthy 7/7

## 2) Mapa de gates (evolucao sem falso green)

| Gate | Total | Quando | Adiciona |
|------|-------|--------|----------|
| 150/150 | 150 | P6-C + T1 5c54440 | ATUAL base ate T1 |
| 167/167 | 167 | P8 v1.0.0 f93578a | +17 W8+X9 docs-only (SLO+THREAT+PERF docs+HNSW S5) — FECHADO |
| 175/175 | 175 | T2 P7 PERF v1.1.0 | +8 W real (cProfile.prof/.txt + bench p95 + evals 6/6 + otim 3 + re-valida) |

Regra: nunca 175 sem 167/167 2x + 21/21 2x equal:true + 7/7 healthy + 40 passed + compose RC0 + promtool SUCCESS.

## 3) T2 detalhado — 4 sub-tarefas (60m)

### T2.1 Profiling hot paths (15m, HPP cap1)

- **T2.1a (5m) cProfile:** `python -m cProfile -o reports/p7-cprofile.prof scripts/bench_hnsw.py` + pstats sort cumtime 20 linhas -> `reports/p7-cprofile.txt`. Gate W1: prof exists + txt has cumtime. Axiom #4: nao mexer em persistencia.
- **T2.1b (5m) Identificar hot paths:** docs/PERF_TUNING.md sec1 tabela: ToolExecutor sleep(2) ~12%, json dumps/_to_chroma_metadata ~8%, WeakValueDictionary ~5%. Medir % total pstats. Nao editar codigo ainda. HPP cap2.
- **T2.1c (5m) Histograma baseline re-run:** `python scripts/bench_hnsw.py 30 queries ef 64 vs 200` -> `reports/p7-bench.log` p50/p95/p99 por ef. Validar `histogram_quantile(0.95, sum(rate(bucket[5m])) by (le))` (Livro4 cap6). Gate W3 parcial.

### T2.2 Otimizacao sem regressao (20m, HPP cap2-3 + Fluent 19-21 + Axiom #2)

- **T2.2a (8m) Polling sleep(2) -> event-driven:** trocar busy sleep(2) por `asyncio.Event` / `XREADGROUP block 5000ms` event-driven. Nunca quebrar PolicyEngine/thread_id/HITL/_build_filter. Se quebrar, revert + documentar SLO 2s em PERF_TUNING.
- **T2.2b (6m) json dumps memoize:** `functools.lru_cache 1024` ou `orjson` se ganho >10% pstats, mantendo redact_pii 2 camadas (CIPHER-025). Nunca user_id em labelnames (Livro4 cap5, re.search labelnames.*user_id).
- **T2.2c (6m) WeakValueDictionary cache se hot >5%:** `WeakValueDictionary` + `memory_profiler` valida RAM nao cresce. Gate W5-W7: apos CADA micro-otim rodar `py_compile+compileall+guard 6/6+verify 21/21 2x+deep 167/167` verdes. Se falhar, revert imediato (SWE cap14).

### T2.3 Evals 6 memory types (15m, Building LLM Apps + awesome-llm-apps 135k)

- **T2.3a (8m) Criar evals/test_memory_types.py:** 6 tipos episodic/semantic/procedural/operational + short_term/long_term/vector (src/jefrey/memory). Cada 20 casos, assert `p95 <2x baseline` + `recall@5 >0.7`. Usa chroma local nomic-embed-text 768 + pgvector 768 (sem modelo pago, free-for-dev ref). Pattern awesome-llm-apps 135k.
- **T2.3b (4m) Rodar:** `python -m pytest evals/test_memory_types.py -q` -> 6/6 passed. Salvar `reports/p7-evals.log` p95 por tipo.
- **T2.3c (3m) PERF_TUNING sec2:** tabela 6 tipos x p95 x ganho vs baseline x custo (ollama 30B placa dedicada vs API — 10 repos R$0 licenca != R$0 custo). Se <5% GO/NO-GO ja coberto; se >=5% documentar ganho.

### T2.4 Gate 175/175 (10m, SWE cap14)

- **T2.4a (5m) Deep +8 gates W real em scripts/_validate_deep.py:** W1 cProfile.prof exists + W2 pstats 20 linhas cumtime + W3 bench p95 log exists + W4 evals 6/6 log exists + W5 otim docs + W6 guard/verify re-valida + W7 deep 175 + W8 docs/PERF_TUNING sec2 tabela 6 tipos. Todos com fail-closed: missing => bugs.
- **T2.4b (5m) Commit + tag v1.1.0:** `git add reports/p7-* evals/test_memory_types.py docs/PERF_TUNING.md scripts/_validate_deep.py` + `git commit -m "feat(P7): PERF v1.1.0 167->175 cProfile+evals+otim (HPP+Fluent+DDIA, 175/175)"` + `git tag v1.1.0` + `git push --tags` (D5). Gate final: 175/175 WARNS0 BUGS0 + 21/21 2x + 40 passed + promtool 6/6 + compose RC0 + 7/7 healthy 2x idempotente.

## 4) Ordem de fechamento ate P8 (ja feito) + T2

- **Feito (Ordem B):** T1 15m hardening -> T3 60m TAG 167/167 v1.0.0 (HEAD f93578a) — P7 deferido.
- **Agora:** T2 60m PERF 167->175 v1.1.0 (se <5% so docs, se >=5% otim real) — D5 push tags v1.0.0-p5-c + v1.0.0 + v1.1.0.
- **Nunca:** C) paralela T2+T3 — alto risco dessync (SWE cap14).

## 5) Sincronismo do projeto (DDIA cap6 + Livro4 cap5/6/10/11)

- **Compose:** 7 servicos 1 rede, 7 healthchecks, 8 envs ?required fail-closed, :ro + tmpfs, ports 8000/8001/3000/9090/5678/5432.
- **Observabilidade:** 18 metrics <800 series, 6 alerts for/severity/slo, 8 panels by(le):2 editable:false, promtool check/test SUCCESS, cardinality sem user_id.
- **Data:** HNSW CONCURRENTLY m16 ef64 AUTOCOMMIT + Streams maxlen10000 DLQ 5000 XACK + kid v1/v2 dual-verify + backup pg_dump/BGSAVE.
- **Qualidade:** py_compile + compileall + guard 6/6 + verify 21/21 2x + deep 175/175 + pytest 40 + metrics_no_user_id.

## 6) Checklist qualidade pre-commit T2 (SWE cap8)

- [ ] py_compile OK
- [ ] compileall -q src RC0
- [ ] guard_anti_patterns 6/6 PASS
- [ ] metrics labelnames.*user_id ==0 (Livro4 cap5)
- [ ] guard_grafana by(le) >=2 editable false
- [ ] verify 21/21 2x equal:true
- [ ] deep 175/175 WARNS0 BUGS0 2x idempotente
- [ ] pytest 40 passed (evals 6/6 separado)
- [ ] promtool check 6 rules SUCCESS + test SUCCESS
- [ ] compose config -q RC0 + docker ps 7/7 healthy

## 7) Uso pos T2 (mesmo do leigo)

`scripts/start_jefrey.bat` (Win) ou `scripts/start_jefrey.sh` (Linux) -> http://localhost:8000/docs + :3000 + :9090 + :5678 + python bench/drill. Troubleshooting FAIL-CLOSED em docs/GUIA_LEIGO_JEFREY.md.
