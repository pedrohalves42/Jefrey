# Aceite P0 -> P1 - Jefrey

> **Etapa 6.5 - Tracer Bullet Final P0 | AXIOM + CIPHER | Gate para P1**
> **Data:** 2026-08-31 08:54 -03:00  |  **Commit:** `f9cbfa2117c8ada594f0b2b55879219ff579dbb8`  |  **Commit date:** 2026-08-30 15:55:27 -0300
> **Modo:** DEV (`JEFREY_DEBUG=true`, `ollama` `llama3.1:8b` / `nomic-embed-text` 768)  |  **Executor:** Pedro (CTO)
> **Suite 6.4:** `python scripts/run_tests.py --ci` -> **5 PASS / 0 FAIL / 116.9s** (2026-08-31)

---

## 1. Objetivo deste documento

Transformar provas tecnicas reproduziveis (logs, `junit.xml`, `docker compose config`) em **aceite auditavel** P0->P1 com 3 percentuais ponderados e gates binarios. Sem este aceite, P0 nao avanca para P1 (Kleppmann: baseline versionado; Pragmatic: broken windows).

**Formula de referencia (DRY em `scripts/compute_readiness.py`):**

```
Peso por dominio (soma 100): Config 10, Postgres 20, Redis 10, Agent 20, Skills 15, EventBus 5, Policy/HITL 10, Infra 10
Fator status: READY=1.0, PARTIAL=0.6, PLACEHOLDER=0.2, BROKEN/NOT_IMPLEMENTED/NOT_VERIFIED=0.0
Implementacao = Soma(peso x fator)/100
Producao     = Implementacao x fator_infra (0.73 se docker+healthchecks OK, senao 0.5)
Comercial    = Producao x 0.90  (fator go-to-market pos-P0; sobe com P1 OAuth/UI)
```

---

## 2. Tabela de Status Real P0 (6 estados canonicos)

| Dominio | Funcionalidade | Status | Prova (comando/log reproduzivel) | CIPHER | Risco P1 |
|---|---|---|---|---|---|
| **Config/Secrets** | `JEFREY_API__SECRET_KEY` hex32 len>=32, `JEFREY_DATABASE__PASSWORD`, `GRAFANA_PASSWORD`, `env_file [.env]` em 3 servicos | **READY** | `python scripts/verify_env.py` -> `PASS secret_key len=64` / `PASS db_password len=6` / `PASS grafana_password len=16` ; `python scripts/setup.py --check` PASS 9.1s ; `docker compose config --quiet` OK | 019, 002, 001 | Baixo |
| **Postgres+pgvector** | 6 camadas memoria (episodic/semantic/preference/procedural/operational/working), `metadata_json JSONB json_path_ops`, HNSW cosine, `embedding_dim 768`, `pg_typeof=jsonb` | **READY** | `python scripts/verify_p1.py` 14.0s PASS: insert/search/ranking `top-1 sim` + filter `tags $in` + filter `metadata_json eq/$in` + update/delete/count ; `init_db()` + `TRUNCATE` deterministico | - | Baixo |
| **Redis Working Memory** | `RedisWorkingMemory` session persistence, `token_count`, `SCAN count=100` (nao `KEYS`), fallback local, `requirepass jefrey_redis_2026`, DSN `redis://:...@localhost:6379/0`, healthcheck `ping || ping -a` | **READY** | `verify_p1` `wm len==2 token_count` + `session preserve` ; `run_tests --ci` PASS ; `SCAN` em `src/jefrey/core/redis_memory.py:166` | 004 | Baixo |
| **Agent LangGraph** | `AgentState` (messages, user_input, current_step, tool_calls, tool_results, memory_context, error, metadata, thread_id, user_id), grafo `load_context->reasoning->execute_tools->save_memory->format_response->END`, `health_check`, OpenAIAgent facade | **READY** | `python -m scripts.smoke_test` 56.5s: `Agente OK - Status: healthy` ; `verify_p2.py` 27.4s PASS: checkpointer Postgres, persistencia entre turnos, Policy RBAC | 018 (tool_timeout 30.0) | Baixo |
| **Skills** | `notes` CRUD (save/search/list/delete), `automation` (READY), `web_search` (Tavily), `calendar/email` (google-api) | **PARTIAL** | `smoke` `Skills: >=2 carregadas, save_note/search_notes OK` ; `notes CRUD completo` PASS ; `web_search` SKIP sem `TAVILY_API_KEY` (tolerado), `calendar/email` PLACEHOLDER sem credenciais | - | Medio - P1 precisa OAuth Google |
| **EventBus** | Async `register/unregister/emit`, handlers lista (nao `WeakSet`), wildcards `on_any`, `emit` sobre copia `_handlers[:]` | **READY** | `smoke` `Event Bus: handlers e wildcards funcionando` PASS ; `verify_p1/p2` sem GC de handler | - | Baixo |
| **Policy/HITL** | Policy Engine `mode enforce/audit/off`, RBAC, rate-limiting, `ApprovalManager` TTL 1800s `poll_interval 2.0 wait_for_decision`, `audit_fallback.jsonl` | **PARTIAL** | `verify_p2` Policy RBAC/HITL health OK ; `config.py` `PolicySettings/HITLSettings` ; falta rate-limit distribuido + HITL polling integrado ao loop (P1) | 018, 025 | Medio |
| **Infra/Observabilidade** | Docker stack 8 servicos (postgres pgvector 5432, redis 6379, api 8000, mcp 8001, n8n 5678, prometheus 9090, grafana 3000), `docker-compose.yml env_file [.env]`, `.github/workflows/test.yml` (pgvector+redis, cache pip, `run_tests --ci`), `reports/junit.xml` + `test_run_*.md`, `.gitignore reports/test_run_*.md+junit.xml !.gitkeep` | **PARTIAL** | `docker compose config --quiet` OK (7 containers) ; `run_tests --ci` 5 PASS + JUnit `tests=5 failures=0` ET.parse OK ; `py_compile` 4 scripts OK ; Prometheus/Grafana UP mas sem dashboards custom | - | Medio - P1 dashboards + alerts |

**Legenda:** READY = codigo + teste verde + CIPHER OK + docs | PARTIAL = funciona com fallback/pendencia P1 | PLACEHOLDER = stub compila mas nao opera | BROKEN/NOT_IMPLEMENTED/NOT_VERIFIED = bloqueia gate se em P0-block.

---

## 3. Percentuais Auditaveis (pesos funcionais, nao LOC)

> Calculado por `python scripts/compute_readiness.py` (pesos acima). Valores travados em 2026-08-31 pos-6.4.

| Metrica | Formula | Valor 2026-08-31 | Delta | Observacao |
|---|---|---|---|---|
| **Implementacao** | Soma(pesoxfator)/100 | **86.0%** | +43% vs auditoria inicial 43% | 5 READY (60 peso x1.0) + 3 PARTIAL (40 peso x0.6) = 86/100 |
| **Prontidao Producao** | Implementacao x 0.73 (infra OK) | **62.8%** | +31% vs 31% inicial | `fator_infra=0.73` porque docker+healthchecks+verify_env verdes |
| **Prontidao Comercial** | Producao x 0.90 | **56.5%** | +28% vs 19% inicial (pico 28% apos 6.3, agora 56.5% com P0 completo) | Fator 0.90 = go-to-market pos-P0 sem OAuth/UI; meta P1 ~70% |

**Detalhamento por dominio:**

| Dominio | Peso | Status | Fator | Contribuicao |
|---|---|---|---|---|
| Config/Secrets | 10 | READY | 1.0 | 10.0 |
| Postgres+pgvector | 20 | READY | 1.0 | 20.0 |
| Redis Working Memory | 10 | READY | 1.0 | 10.0 |
| Agent LangGraph | 20 | READY | 1.0 | 20.0 |
| Skills | 15 | PARTIAL | 0.6 | 9.0 |
| EventBus | 5 | READY | 1.0 | 5.0 |
| Policy/HITL | 10 | PARTIAL | 0.6 | 6.0 |
| Infra/Observabilidade | 10 | PARTIAL | 0.6 | 6.0 |
| **Total** | **100** | - | - | **86.0** |

> **Nota historica:** Auditoria master inicial reportava `Implementacao 43% -> Producao 31% -> Comercial 19%` (pre-P0 fixes). Apos P0 fixes (CIPHER-019/002, KeyError, EventBus weakref, JSONB, Redis DSN) + Etapa 6 (6.1 UTF-8, 6.2 JSONB, 6.3 .env+setup, 6.4 suite) -> **86.0% / 62.8% / 56.5%**. O salto reflete que P0-blocks sairam de BROKEN para READY.

---

## 4. Gates P0->P1 (binarios - fail-closed, Anderson)

| Gate | Condicao | Resultado 2026-08-31 | Prova |
|---|---|---|---|
| **G1 - P0-blocks** | `READY+PARTIAL == 100%` nos 8 dominios P0-block, zero `BROKEN/PLACEHOLDER/NOT_VERIFIED` em P0-block | **PASS** | Tabela acima: 5 READY + 3 PARTIAL = 8/8 (100%), nenhum P0-block em PLACEHOLDER/BROKEN |
| **G2 - Suite 6.4** | `run_tests.py --ci == 5 PASS 0 FAIL` + `verify_env PASS` | **PASS** | `--ci 5 PASS 116.9s` (setup 9.5s, verify_env 9.2s, smoke 59.6s, verify_p1 14.2s, verify_p2 24.3s) ; `verify_env: PASS secret_key 64 / db_password / grafana / service_role / dsn` |
| **G3 - Infra** | `docker compose config --quiet ==0` + `py_compile 4 scripts OK` + `junit.xml ET.parse OK` | **PASS** | `docker compose config --quiet` OK (7 containers) ; `py_compile run_tests/smoke/verify_env/redis_memory OK` ; `junit.xml tests=5 failures=0 skipped=0` |

**Decisao:** [OK] **P0 ACEITO - LIBERADO PARA P1.** Se qualquer gate falhar, P0->P1 = FAIL (nao comercializavel).

---

## 5. Reproducao Fresh Machine (tracer bullet 6.4)

Copiar e colar em maquina limpa (Windows/Linux) com Docker + Python 3.11:

```bash
git clone <repo> && cd jarvis
git rev-parse HEAD  # deve bater com commit deste aceite: f9cbfa2117c8ada594f0b2b55879219ff579dbb8
python scripts/setup.py --dev --non-interactive --force
docker compose up -d --wait
python scripts/run_tests.py --ci      # espera 5 PASS ~115s
python scripts/run_tests.py --quick   # 2 PASS ~40s (smoke rapido)
python scripts/verify_env.py          # PASS secret_key/db_password/grafana/dsn
python scripts/compute_readiness.py   # 86.0% / 62.8% / 56.5%
python -c "import xml.etree.ElementTree as ET; ET.parse('reports/junit.xml'); print('junit OK')"
docker compose config --quiet && echo "compose OK"
```

Artefatos gerados: `reports/test_run_*.md` (Rich table + tempos) + `reports/junit.xml` + `reports/.gitkeep` (versionado, resto ignorado via `.gitignore`).

---

## 6. O que falta para Comercial ~70% (P1 - proximo marco)

| P1 Item | Peso que vira READY | Ganho comercial |
|---|---|---|
| OAuth Google Calendar & Gmail (token 0o700, refresh) | Skills PARTIAL->READY (+6.0 impl) | +5.4% comercial |
| HITL polling integrado ao loop + rate-limiting distribuido | Policy PARTIAL->READY (+4.0) | +3.6% |
| UI chat + dashboards Grafana + alerts Prometheus | Infra PARTIAL->READY (+4.0) | +3.6% |
| Testes E2E + backup/restore automatizado | + robustez | +2% |
| **Meta P1** | **Impl 100% / Prod 73% / Comercial ~70%** | **+15%** |

---

## 7. Assinatura

| Campo | Valor |
|---|---|
| **Aceite em** | 2026-08-31 08:54 -03:00 |
| **Commit** | `f9cbfa2117c8ada594f0b2b55879219ff579dbb8` |
| **Executor** | Pedro (CTO) |
| **Modo** | DEV (DEBUG=true, ollama 768) - PROD exige `JEFREY_DATABASE__PASSWORD` forte + `SECRET_KEY` 64 + `GRAFANA_PASSWORD` != CHANGE_ME |
| **Proximo marco** | P1 OAuth/HITL/UI (meta Comercial ~70%) |

**Assinatura CTO:** _________________________  **Data:** ____/____/______

---

*Gerado via Etapa 6.5 AXIOM + CIPHER + Kleppmann/Ramalho/Anderson/SWE at Google/Pragmatic/High Performance Python/Prometheus/MCP Spec/OpenAI Agents SDK. Single source: `scripts/run_tests.py` + `scripts/compute_readiness.py`.*
