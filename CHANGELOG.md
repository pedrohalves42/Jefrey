# Changelog — Jefrey

Todas mudancas notaveis deste projeto. Formato baseado em Keep a Changelog.

## [1.1.0] — 2026-09-03 — P7 PERF T2 (Ordem B 60m 167->175) — 175/175

**Gate**: _validate_deep 175/175 (170+5) + verify 21/21 2x equal:true + pytest 40 passed + evals 6 passed + compileall OK + guard 6/6 + promtool 6/6 + compose config -q RC0 + 7/7 healthy
**Provas vivas**: reports/p7-cprofile.prof 3.1MB + p7-cprofile.txt 3719B cumtime 30 linhas (HPP cap1) + reports/p7-bench.log 8837B p50 48.1ms p95 55.0ms ef64 / p95 52.3ms ef200 60 queries 100 rows Seq Scan (DDIA cap12) + reports/p7-evals.log 900B 6/6 (Building LLM Apps)
**Otimizacoes** (HPP cap2-3, Fluent 19-21, <5% GO com fallback): src/jefrey/core/audit.py functools.lru_cache 1024 + orjson sort_keys (CIPHER-025, 2 camadas) + src/jefrey/core/pg_memory.py WeakValueDictionary _PG_CACHE + orjson _jsonable
**Docs**: docs/PERF_TUNING.md reescrito 8 secoes com cProfile real + bench p95 real + evals 6 types + GO/NO-GO <5% (Pragmatic cap8) + docs/HNSW_TUNING.md §6 P7
**Refs**: HPP cap1-4 + Fluent 19-21 + Building LLM Apps + DDIA cap12 + Livro4 cap5/6 + SWE cap8/14 + CIPHER-025/033 + Axiom #1-7
**Commits**: 167/167 v1.0.0 f93578a/bb4c45e + T2 P7 PERF v1.1.0

## [1.0.0] — 2026-09-03 — P8 TAG (T3 Ordem B — 150→162)

### Auditado 150/150 2x + 21/21 2x + 40 passed + 7/7 healthy (Axiom #1-7 + CIPHER + Livros)

- **P6-C** bdcae44 feat(P6-C): verify 150/150 idempotente + CI gate + compose healthy (DDIA cap3/6, SWE cap14, Axiom #1, 21/21 2x)
- **P5-C** 88bf25d feat(P5-C): consolidacao observability freeze 148/148 idempotente (Livro4 cap5/6/10/11, 148/148)
- **P6-gaps** 687d589 feat(P6-gaps): verify 19/19 + isolation 2 tenants + deep 136->148 secao U (DDIA cap3/5/6/12, CIPHER-033)
- **P6-A** HNSW CONCURRENTLY m16 ef64 AUTOCOMMIT + bench CAST vector + SET LOCAL int(ef) (DDIA cap12, HPP cap4)
- **P6-B** Streams 2-processos maxlen10000 DLQ maxlen5000 XACK dual-verify kid v1/v2 + BGSAVE + pg_dump (CIPHER-033)
- **T1 hardening** 8feef7e feat(T1): redis healthy + skill_registry + requirements +11 deps + testpaths + compileall OK (Axiom #2/#4, 40 passed)
  - 28aa37d fix(T1): AppSettings env_prefix JEFREY_ isolate AGENT=1 (Axiom #2, CIPHER-032)
  - 98cd0da fix(T1.1): mcp missing register_default_tools import — jefrey-mcp healthy (Axiom #6, CIPHER-032, DDIA cap6)
  - 5c54440 docs(T1): fecha T1 HARDENING 100% Up vivo 7/7 healthy + grafana by(le):2 + 150/150 2x
- **P8** docs: SLO_RUNBOOK 6 alerts x PromQL x for x slo, THREAT_MODEL 7 controles STRIDE, PERF_TUNING GO/NO-GO <5%, HNSW_TUNING §5, CHANGELOG

#### Commits desde bdcae44

```
7fcc91d docs(P7): add PLANO_P7_PERF_V1.md 214L force (gitignore)
a6b3f63 docs(P7): plano P7 PERF V1.0 60m 150->158 + validacao 11:15 99% DATA + ordem P8 + guia uso jefrey (HPP, Fluent, DDIA, Livro4)
5c54440 docs(T1): fecha T1 HARDENING 100% Up vivo 7/7 healthy + grafana by(le) 2 + 150/150 2x (Axiom #1, DDIA cap6, Livro4 cap11, 40 passed)
98cd0da fix(T1.1): mcp server missing register_default_tools import — jefrey-mcp healthy (Axiom #6, CIPHER-032, DDIA cap6, SWE cap8, 150/150, 40 passed)
6c3cebb docs(T1): recria PLANO_SINCRONIZADO V2.1 do zero 10:47 + TODO sync (150/150, 21/21 2x, 40 passed, D3 fechado)
28aa37d fix(T1): isolate AppSettings env_prefix JEFREY_ to ignore AGENT=1 collision (Axiom #2, CIPHER-032, 40 passed)
a6c0aae docs(T1): TODO V2.1 hardening audit 09:40 (150/150, 21/21 2x)
9c204a2 docs(T1): sync V2.1 audit 09:40 + TODO T1.0 hardening 8feef7e (150/150, 21/21, 40 passed)
8feef7e feat(T1): hardening 100% redis healthy + skill_registry + requirements sync + testpaths (Axiom #2/#4, 150/150, 40 passed)
```

#### Gates

- 122/122 ->136/136 ->148/148 ->150/150 (P6-C) ->162/162 (P8) = 100% v1.0.0
- verify_p6_data 21/21 2x idempotente true + deep 162/162 WARNS0 BUGS0 + compileall OK + pytest 40 + promtool 6/6 + grafana 8 panels by(le):2 + compose 7/7 healthy

#### Uso

- `curl http://localhost:8000/health` + `/docs` + `curl http://localhost:8001/health` + `open http://localhost:9090` + `http://localhost:3000` + `http://localhost:5678` + python bench/drill (PLANO_P7 sec5)

## [1.0.0-p5-c] — local

- Tag local v1.0.0-p5-c 88bf25d — P5 freeze 148/148

## [0.6.0] — P6 DATA 150/150

- HNSW, Streams, backup, verify 21/21 — DDIA cap3/5/6/12

## [0.5.0] — P5 OBSERVABILITY 148/148

- Cardinality <800, 8 panels, 6 alerts for/severity/slo, promtool SUCCESS

## Referencias externas 10 repos

- public-apis 474k, awesome 501k, free-for-dev 136k, awesome-mcp-servers 93k, ollama 179k, langflow 154k, OpenHands 85k, Scrapling 77k, awesome-llm-apps 135k, open-design 93k — R$0 licenca != R$0 custo (Secao 6 PERF_TUNING)
