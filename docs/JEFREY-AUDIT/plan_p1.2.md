# Plano P1.2 -- Policy/HITL + Infra/Observabilidade READY + Stubs + Rate-Limit | AXIOM + CIPHER
> **P1.1 fechado:** 92.0% Impl / 67.2% Prod / 60.4% Comercial (Skills READY) -- commit P1.1 staged
> **Meta P1.2:** 92.0% -> **100% Impl** / 67.2% -> **73.0% Prod** / 60.4% -> **65.7% Comercial** (69.3% GTM ?0.95)
> **Gate:** Policy/HITL PARTIAL->READY (+4.0pp) + Infra PARTIAL->READY (+4.0pp) = +8.0pp
> **Data:** 2026-08-31 | **Base:** ec9cd01 + P1.1 (N1-N6 fechados) | **Stack:** Postgres 16 + pgvector + Redis 7.2 + LangGraph + FastAPI + MCP + n8n + Prometheus + Grafana
> **Livros base:** Kleppmann DDIA ? Ramalho Fluent Python ? Anderson Security Engineering ? SWE at Google ? Pragmatic Programmer ? High Performance Python ? Prometheus Up & Running ? MCP 2026-07-28 ? OpenAI Agents SDK

---

## 1. Estado atual (single source: scripts/compute_readiness.py)

```
WEIGHTS 100: Config 10 + Postgres 20 + Redis 10 + Agent 20 + Skills 15 + EventBus 5 + Policy/HITL 10 + Infra 10
FACTOR: READY 1.0 / PARTIAL 0.6 / PLACEHOLDER 0.2
P0:  86.0% Impl (5 READY 60 + 3 PARTIAL 24)
P1.1:92.0% Impl (6 READY 75 + 2 PARTIAL 12)  -- Skills READY (drive.file + web_search ddgs fallback + OAuth hardening)
P1.2:100% Impl (8 READY 100)                -- Policy/HITL + Infra READY
Prod = Impl ? 0.73 | Comercial = Prod ? 0.90 (GTM ?0.95 = 65.7?0.95=62.4 real, 69.3 sem desconto)
```

```bash
python scripts/compute_readiness.py                         # 92.0/67.2/60.4 (real hoje)
python scripts/compute_readiness.py --status '{"Policy/HITL":"READY"}'          # 96.0/70.1/63.1
python scripts/compute_readiness.py --status '{"Policy/HITL":"READY","Infra/Observabilidade":"READY"}' # 100/73/65.7
```

**2 dominios PARTIAL restantes:**

| Dominio | Peso | Hoje | Falta para READY | Livro chave |
|---------|------|------|------------------|-------------|
| **Policy/HITL** | 10 | PARTIAL (RBAC Policy enforce sem rate-limit; HITL ApprovalManager isolado, nao integrado ao Agent loop) | Rate-limit Redis Lua distribuido + HITL integrado `execute_tools -> wait_for_decision` + audit_fallback + RBAC fino por tool | Anderson (fail-closed) + Kleppmann (consistencia) |
| **Infra/Observabilidade** | 10 | PARTIAL (Prometheus metrics existem, mas sem dashboards/alerts/runbook; backup/restore manual) | 4 dashboards Grafana + 10 alerts Prometheus + runbook + backup/restore pg_dump+BGSAVE + CONFIG_VALID no startup (N2 feito) | Prometheus Up & Running + SWE at Google (SLO) |

---

## 2. Principios AXIOM + CIPHER (fail-closed)

**AXIOM 6 eixos (gate binario):**

1. **Codigo tipado** -- `TypedDict/Final/Literal`, `py_compile` 0 erros, `mypy --strict` soft, ASCII-only, sem `Any` solto (Ramalho).
2. **Teste reproduzivel** -- `python scripts/run_tests.py --ci` 5 PASS + `smoke_test 7/7` + `verify_p1/p2` + `junit.xml`, idempotente fresh machine (Pragmatic, SWE at Google).
3. **Seguranca fail-closed** -- sem credencial -> SKIP nao FAIL, rate-limit nega por default, HITL expira -> `expired` (Anderson, CIPHER-001/002/018/019/025).
4. **Observabilidade** -- Prometheus `Counter/Histogram/Gauge` labels baixa cardinalidade, Grafana dashboards, alerts com `for: 5m` (Prometheus Up & Running).
5. **Documentacao** -- `docs/oauth.md` + `docs/runbook.md` + `docs/JEFREY-AUDIT/acceptance_p1.2.md` + `.env.example` com todos os `JEFREY_*`.
6. **Aceite binario** -- checklist PASS/FAIL sem "quase pronto" (AXIOM).

**CIPHER aplicavel:**

- `001` service_role server-side (`mcp.service_role` em allowed_roles, nunca do caller)
- `002` secrets via `.env`, `config/tokens 0o700`, `config/credentials 0o700`, `token 0o600`, `.gitignore`
- `018` tool_timeout 30.0s (`asyncio.wait_for`)
- `019` `JEFREY_API__SECRET_KEY` len>=32, `CORS_ORIGINS` restrito
- `025` audit_fallback dual-write (`data/audit_fallback.jsonl`)
- `024` HITL TTL 1800s + poll 2.0s

---

## 3. Arquitetura P1.2 (Kleppmann -- single source, idempotencia, ordem)

```
[User] -> FastAPI /chat -> JefreyAgent (LangGraph: load_context -> reasoning -> execute_tools -> save_memory -> END)
                              ?
                              ??-> ToolRegistry(33 tools) -> RBAC (Role.GUEST/USER/ADMIN) -> Policy(mode=enforce/audit/off) -> RateLimit(Redis Lua) -> HITL(ApprovalManager) -> Tool.ainvoke (timeout 30s, audit dual-write)
                              ??-> Memory: ShortTerm(Redis deque RLock) + LongTerm(Postgres pgvector HNSW 768) + Chroma fallback
                              ??-> EventBus (lista normal, emit sobre copia, wildcards) -> n8n /webhook/jefrey-events
                              ??-> Skills: notes/automation (READY) + calendar/email/drive (OAuth PKCE 0o600) + web_search (Tavily+ddgs cache 5m) + notion/whatsapp (P1.2 stubs PLACEHOLDER) + slack/github/seo (P1.2 hardening)

Infra: docker-compose (postgres pgvector / redis / api:8000 / mcp:8001 / n8n:5678 / prometheus:9090 / grafana:3000)
Observabilidade: prometheus_client -> /metrics (PUBLICO) -> Prometheus scrape 15s -> Grafana dashboards + alerts -> runbook
Backup: pg_dump + redis BGSAVE -> data/backups/ (cron)
```

**Invariantes (AXIOM+CIPHER):**

- Todo `tool.ainvoke` passa por `Policy -> RateLimit -> HITL` (nao bypass).
- Rate-limit distribuido: **1 Lua script EVALSHA** (High Performance Python O(1), atomico), fallback local se Redis fora.
- HITL nao trava loop: `wait_for_decision` com `TTL 1800s` -> `expired` -> nega tool.
- Observabilidade nao quebra app: `try: metrics.inc() except: pass`.

---

## 4. Epicos P1.2 (4 epicos, 8-10 dias, depende P1.1)

### E1 -- Rate-Limit Distribuido (Policy/HITL READY 40%)

**Objetivo:** fechar CIPHER-025 + Anderson least privilege com limite por `user_id + tool_name + role`.

**Arquivos:**

- `src/jefrey/core/rate_limit.py` **NOVO** -- `RateLimiter` com `Redis Lua (EVALSHA)`, fallback in-memory `deque` com `RLock`.
  - `Final[int] MAX_TOKENS = 20` por janela `WINDOW_S = 60.0` (configuravel via `JEFREY_POLICY__RATE_LIMIT_MAX` / `WINDOW`).
  - Lua: `local key=KEYS[1]; local now=ARGV[1]; local window=ARGV[2]; local max=ARGV[3]; redis.call('ZREMRANGEBYSCORE',key,0,now-window); if redis.call('ZCARD',key) < tonumber(max) then redis.call('ZADD',key,now,now); redis.call('EXPIRE',key,window); return 1 else return 0 end`
  - Labels: `jefrey_rate_limit_total{tool_name, decision=allow|deny}` (Counter).
  - TypedDict `RateLimitConfig`, `Final`, `Literal["allow","deny"]`.
  - High Performance Python: ZSET O(log N) + EXPIRE atomico, bounded, SCAN nao needed.
- `src/jefrey/core/config.py` -- `PolicySettings.rate_limit_max: int = 20`, `rate_limit_window: float = 60.0` (env `JEFREY_POLICY__RATE_LIMIT_*`).
- `src/jefrey/core/registry.py` -- `ToolRegistry.register` adiciona `rate_limit_key` opcional.
- `src/jefrey/core/policy.py` -- integra `RateLimiter.is_allowed(user_id, tool_name)` antes de HITL; se deny -> `TOOLS_BLOCKED.labels(tool_name, reason="rate_limit").inc()`.

**Seguranca:** deny por default se Redis fora? **Nao** -- fail-open para rate-limit (degrada para in-memory) mas **fail-closed** para auth/HITL. Distinto (Anderson).

**Teste:** `scripts/verify_p1.py` + novo `tests/test_rate_limit.py` (20 req ok, 21a deny, janela expira -> allow).

---

### E2 -- HITL Integrado ao Agent Loop (Policy/HITL READY 40%)

**Objetivo:** HITL nao mais isolado; `Agent._execute_tools` chama `ApprovalManager.wait_for_decision`.

**Arquivos:**

- `src/jefrey/core/hitl.py` -- j? tem `ApprovalManager(TTL 1800, poll 2.0)`, `ApprovalDecision(approved/rejected/expired)`. **Adicionar:** `create_approval(tool_name, user_id, args, risk_level) -> id`, `wait_for_decision(id) -> Decision` com polling + timeout, metric `APPROVALS_CREATED/DECIDED`.
- `src/jefrey/core/agent.py` -- `_execute_tools`: para cada `tool_call` com `RiskLevel.MEDIUM|HIGH`, se `policy.mode=enforce` -> `approval_id = await hitl.create_approval(...)` -> `decision = await hitl.wait_for_decision(id)` -> se `approved` -> `tool.ainvoke`, senao retorna `{"error":"denied","reason":decision}`. Se `mode=audit` -> loga mas executa. Se `off` -> bypass.
- `src/jefrey/api/approvals.py` -- j? tem `build_approvals_app()` (Starlette /approvals). **Hardening P1.2:** dual-write audit: tenta Postgres `audit_logs`, fallback `data/audit_fallback.jsonl` (CIPHER-025), `audit_fallback_path` 0o600.
- `src/jefrey/core/executor.py` -- `ToolExecutor` envolve `rate_limit + hitl + timeout 30s + audit`.

**Seguranca:** `service_role` server-side, nunca do payload (CIPHER-001). `secret_key` valida Bearer.

**Teste:** `scripts/verify_p2.py` ja testa checkpointer; adicionar HITL flow em `smoke_test.py` ?8.

---

### E3 -- Infra/Observabilidade READY (Infra 10 -> READY)

**Objetivo:** fechar Prometheus Up & Running + SWE at Google SLO.

**Arquivos:**

- `src/jefrey/core/metrics.py` -- j? tem `SKILL_INIT_TOTAL, OAUTH_REFRESH_TOTAL, WEB_SEARCH_CACHE_HIT, CONFIG_VALID, SERVICE_HEALTH`. **P1.2 adiciona:** `RATE_LIMIT_TOTAL (Counter tool_name, decision)`, `HITL_QUEUE_GAUGE (Gauge)`, `BACKUP_LAST_SUCCESS (Gauge timestamp)`.
- `src/jefrey/api/main.py` -- j? tem N2 `CONFIG_VALID.set` (P1.1). **P1.2:** adiciona `startup_event` que registra `SERVICE_HEALTH=1`, `Uptime` e exp?e `/metrics` (j? existe via `metrics_endpoint`). Verifica `docker-compose.yml` j? tem `prometheus:9090` + `grafana:3000`.
- `prometheus/prometheus.yml` -- j? existe? Verificar; se nao, criar scrape `api:8000/metrics` 15s.
- `grafana/dashboards/jefrey-overview.json` **NOVO** + `jefrey-skills.json` + `jefrey-hitlt.json` + `jefrey-infra.json` (4 dashboards) -- panels: LLM latency p95, tokens, tools_blocked, approvals, skill_init, oauth_refresh, cache_hit, service_health, config_valid, rate_limit, memory_ops.
- `prometheus/alerts.yml` **NOVO** -- 10 alerts: `HighLLMLatency`, `HighToolsBlocked`, `ApprovalsQueueHigh`, `ServiceDown`, `ConfigInvalid`, `RedisDown`, `PostgresDown`, `RateLimitHigh`, `BackupStale`, `MCPDown` (for 5m, severity warning/critical).
- `docs/runbook.md` **NOVO** -- tracer bullet: `python scripts/setup.py --dev --non-interactive --force && docker compose up -d --wait && python scripts/run_tests.py --ci`; runbook por alerta (ex: ConfigInvalid -> `python scripts/verify_env.py`).
- `scripts/backup.py` + `scripts/restore.py` **NOVO** -- `pg_dump` + `redis BGSAVE` -> `data/backups/jefrey_%Y%m%d.sql` + `dump.rdb`, metric `BACKUP_LAST_SUCCESS`, cron exemplo, docs.
- `.env.example` -- adicionar `JEFREY_POLICY__RATE_LIMIT_MAX=20`, `JEFREY_POLICY__RATE_LIMIT_WINDOW=60`.

**Teste:** `promtool check rules prometheus/alerts.yml`, `grafana` health, `backup.py --check`.

---

### E4 -- Skills: Notion/WhatsApp Stubs + Slack/GitHub/SEO Hardening (Skills READY mantem 100%)

**Objetivo:** manter Skills READY (ja 92%->100% via Policy/Infra) mas **curar** backlog 86 skills sem quebrar gate. Stubs PLACEHOLDER nao penalizam, mas preparam P1.3.

**Curadoria 86 skills (guia 3z36c) link:**

- Marketing 45 + Social 17 + Design 3 (ui-ux-pro-max 122k) + Financeiro 8 + Juridico 9 + Documentos 4 = 86.
- **P1.1 fechou:** calendar/email/drive/web_search (4 skills, least privilege).
- **P1.2 faz:**
  - **Stubs PLACEHOLDER (nao contam peso, mas versionados):**
    - `src/jefrey/skills/notion.py` -- `NotionSkill` PLACEHOLDER (TypedDict `NotionPage`, `SCOPES`, `initialize()->False`, `get_tools()->[]`, 0 tools registradas, metric skip). Usa `JEFREY_INTEGRATIONS__NOTION__TOKEN` (ja em config.py). Documenta em `docs/oauth.md` como PLACEHOLDER. Peso nao muda, mas prepara P1.3.
    - `src/jefrey/skills/whatsapp.py` -- idem PLACEHOLDER (Baileys/n8n webhook stub).
  - **Hardening PARTIAL->READY candidatos (se tempo, senao P1.3):**
    - `slack` / `github` / `seo` -- so se couber em 8 dias; senao ficam backlog documentado em `plan_p1.2.md` ? backlog.

**Arquivos:**

- `src/jefrey/core/config.py` -- j? tem `NotionSettings` (enabled/token). Adicionar `WhatsAppSettings` se nao existe? Verificar; se nao, adicionar `class WhatsAppSettings(BaseSettings): enabled bool, webhook_url str`.
- `src/jefrey/skills/notion.py`, `whatsapp.py` -- stubs com `SkillMetadata(name, requires_auth=True, enabled_by_default=False)`, `SCOPES: Final`, `initialize()->False`, `get_tools()->[]`.
- `src/jefrey/skills/__init__.py` -- registra stubs condicionalmente (se `JEFREY_SKILLS__NOTION=true`).
- `docs/oauth.md` -- sec??o `Notion/WhatsApp (PLACEHOLDER P1.2)`.

**Seguranca:** stubs nao exp?em credencial, `get_tools()->[]` garante RBAC nao precisa avaliar.

---

## 5. Matriz de rastreabilidade (todo projeto linkado)

| Componente | P1.1 (92%) | P1.2 (100%) | Arquivos tocados | AXIOM | CIPHER | Livro |
|------------|------------|-------------|------------------|-------|--------|-------|
| Config/Secrets 10 | READY | READY | `config.py` (+ rate_limit, whatsapp), `.env.example`, `.gitignore` | 1,3 | 002,019 | Kleppmann |
| Postgres+pgvector 20 | READY | READY | `models.py` (JSONB), `pg_memory.py`, `backup.py` | 1,2 | 002 | Kleppmann |
| Redis 10 | READY | READY | `redis_memory.py` (SCAN), `rate_limit.py` (Lua) | 1,4 | 025 | High Perf Python |
| Agent 20 | READY | READY | `agent.py` (+ HITL), `executor.py`, `openai_agent.py` | 1,2,3 | 001,018 | OpenAI SDK |
| Skills 15 | **READY** | **READY** (stubs) | `drive.py, web_search.py (N1-N4), notion.py, whatsapp.py` | 1,2,3,4,5 | 019 | Ramalho |
| EventBus 5 | READY | READY | `events.py` | 1 | - | Kleppmann |
| Policy/HITL 10 | PARTIAL | **READY** | `policy.py, hitl.py, rate_limit.py, approvals.py, registry.py` | 1,2,3,4 | 001,018,019,025 | Anderson |
| Infra 10 | PARTIAL | **READY** | `metrics.py, api/main.py, prometheus.yml, grafana/*.json, alerts.yml, backup.py, runbook.md` | 4,5,6 | 025 | Prometheus |

---

## 6. Implementacao passo-a-passo (ordem Kleppmann -- sem quebrar main)

**Dia 1-2 -- E1 Rate-Limit:**

1. Criar `src/jefrey/core/rate_limit.py` (TypedDict, Final, Lua EVALSHA, fallback deque RLock, Counter).
2. Estender `PolicySettings` em `config.py`.
3. Integrar em `policy.py` antes de HITL.
4. Teste: `python -m pytest tests/test_rate_limit.py -v` + `scripts/verify_p1.py` (nao regressao).

**Dia 3-4 -- E2 HITL integrado:**

1. Hardening `hitl.py` + `executor.py` + `agent.py` (RiskLevel check, wait_for_decision, metrics).
2. Dual-write audit em `approvals.py`.
3. Teste: `python -m scripts.smoke_test` + novo teste HITL em smoke (?8).

**Dia 5-6 -- E3 Infra:**

1. Estender `metrics.py` + `api/main.py` startup.
2. Criar `prometheus/prometheus.yml`, `grafana/dashboards/*.json`, `prometheus/alerts.yml`, `docs/runbook.md`, `scripts/backup.py|restore.py`.
3. Teste: `promtool check rules`, `docker compose up -d --wait`, `curl localhost:9090/-/healthy`, `curl localhost:3000/api/health`.

**Dia 7 -- E4 Stubs + hardening:**

1. Criar `notion.py`, `whatsapp.py` PLACEHOLDER, registrar condicional.
2. Atualizar `docs/oauth.md` + `.env.example`.
3. Se sobrar tempo: slack/github/seo hardening (senao backlog P1.3).

**Dia 8 -- Gate:**

1. `python -m py_compile` 8 arquivos.
2. `python scripts/setup.py --dev --non-interactive --force && docker compose up -d --wait && python scripts/run_tests.py --ci` -> 5 PASS + junit.
3. `python scripts/compute_readiness.py --status '{"Policy/HITL":"READY","Infra/Observabilidade":"READY"}'` -> 100/73/65.7.
4. Gerar `docs/JEFREY-AUDIT/acceptance_p1.2.md` + commit.

---

## 7. Checklist AXIOM 6 eixos -- gate P1.2->P1.3 (binario)

- [ ] **Codigo:** `py_compile` 10 arquivos OK (rate_limit, hitl, policy, agent, executor, approvals, metrics, api/main, notion, whatsapp), TypedDict/Final/Literal, ASCII-only, sem BOM
- [ ] **Teste:** `setup --check PASS` 12s + `verify_env PASS` + `smoke 8/8 PASS` + `verify_p1/p2 PASS` + `run_tests --ci 5 PASS` + `junit.xml` 0 failures
- [ ] **Seguranca:** `verify_env PASS` (secret_key 64, password, grafana), `config/tokens 0o700` (Linux), `.gitignore` tokens/credentials, rate-limit deny metric, HITL TTL 1800, audit dual-write, less privilege (drive.file, notion token env)
- [ ] **Observabilidade:** `CONFIG_VALID=1.0` no startup, `RATE_LIMIT_TOTAL`, `HITL_QUEUE`, `BACKUP_LAST_SUCCESS`, 4 dashboards Grafana OK, 10 alerts `promtool check` OK, `/metrics` scrape 15s
- [ ] **Documentacao:** `docs/oauth.md` (Notion/WhatsApp PLACEHOLDER + Nota Windows), `docs/runbook.md`, `docs/JEFREY-AUDIT/acceptance_p1.2.md`, `README.md` tracer +`P1.2 READY 100/73/65.7` banner, `.env.example` completo
- [ ] **Aceite:** `compute 100/73/65.7` com override, `git log` mostra P1.2 commit, fresh machine `setup --dev --force && compose up --wait && run_tests --ci` PASS

**Gate PASS se todos acima PASS.** Falha em 1 -> FAIL.

---

## 8. Riscos e mitigacao (Pragmatic, SWE at Google)

| Risco | Prob | Impacto | Mitigacao |
|-------|------|---------|-----------|
| Redis Lua indisponivel (HELLO auth fail) | M | Rate-limit falha | Fallback in-memory deque RLock (High Performance Python), metric skip, nao bloqueia tool (Anderson: fail-open para rate, fail-closed para auth) |
| HITL deadlock (humano nunca decide) | M | Agent trava | TTL 1800s -> expired -> deny + metric, poll 2.0s com timeout 30s (CIPHER-018) |
| Prometheus/Grafana nao sobem em Windows | L | Infra nao validada | `docker compose up -d --wait` + healthcheck, docs/runbook com `curl` fallback, CI exige Linux (ubuntu-latest) |
| Backup pg_dump exige credencial | L | Backup FAIL | `scripts/backup.py --check` SKIP nao FAIL sem credencial (idem skills), documenta em runbook |
| Scope creep (slack/github/seo) | H | Atraso 8 dias | E4 hardening ? **stretch**; stubs notion/whatsapp sao obrigatorios, resto backlog P1.3 documentado |

---

## 9. Estimativa e dependencias

- **Duracao:** 8 dias (2+2+2+1+1) -- 1 dev senior, 6h/dia focado.
- **Dependencias:** P1.1 staged (92% ok), Docker (postgres pgvector, redis 7.2, prometheus, grafana), Ollama llama3.1:8b (ou OpenAI), `pip install ddgs tavily-python google-api`.
- **Ordem:** E1 -> E2 -> E3 -> E4 (Kleppmann: construir base antes de topo; nao paralelizar E1/E2 sem E1 pronto).
- **Custo:** 0 infra extra (usa compose existente), tempo humano 48h.

---

## 10. Backlog P1.3+ (pos 100% Impl, rumo 70% comercial real)

- **P1.3 Skills hardening:** Slack (chat.postMessage), GitHub (repo.read), SEO (tavily+serp), Financeiro/Juridico/Documentos (oficiais Anthropic, exigem RBAC fino + revisao humana).
- **P1.4 UI:** chat streaming `/chat/stream` + frontend.
- **P1.5 CI 7 steps:** ruff/mypy/black/isort + pytest + docker build.
- **P1.6 Backup/restore automatizado + SLO 99.5%.**

---

## 11. Comando tracer bullet (reproduzivel fresh machine)

```bash
python scripts/setup.py --dev --non-interactive --force
docker compose up -d --wait
python scripts/verify_env.py          # PASS + WARN 777 Windows (N5)
python scripts/compute_readiness.py   # 92.0 P1.1 real
python scripts/compute_readiness.py --status '{"Policy/HITL":"READY","Infra/Observabilidade":"READY"}' # 100/73/65.7 P1.2
python -m scripts.smoke_test          # 8/8 PASS (7 + HITL)
python scripts/run_tests.py --ci      # 5 PASS 93.7s + junit.xml
# Grafana: http://localhost:3000 (admin/admin) -> Dashboards -> Jefrey Overview
# Prometheus: http://localhost:9090 -> Alerts -> 10 firing check
```

---

## 12. Aceite P1.2 -> P1.3

Gerar `docs/JEFREY-AUDIT/acceptance_p1.2.md` com:

- Pesos 100/73/65.7 prova
- Tabela 4 epicos + 6 eixos PASS
- `reports/test_run_*.md` + `junit.xml` anexos
- Banner `README.md`: `**P1.2 READY 2026-08-31 -- 100%/73.0%/65.7% -- Policy/HITL+Infra READY -- gate P1.2->P1.3 PASS**`

**Proximo:** executar P1.2 com AXIOM+CIPHER e livros base, garantindo minimo erro logica/sintaxe (TypedDict/Final, py_compile, fail-closed, observabilidade, docs, aceite binario) e linkando todo projeto (config->agent->policy->hitl->redis->postgres->grafana->backup).
