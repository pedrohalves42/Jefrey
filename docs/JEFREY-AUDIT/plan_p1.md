# Plano P1 — Jefrey | AXIOM + CIPHER + Livros Base
> **Gate P0->P1: ACEITO 2026-08-31 — 86.0% Impl / 62.8% Prod / 56.5% Comercial (infra 0.73)**
> **Meta P1: 100% Impl / 73.0% Prod / 65-70% Comercial — 3 dominios PARTIAL -> READY**
> **Base: Kleppmann DDIA, Ramalho Fluent Python, Anderson Security, SWE at Google, Pragmatic, High Performance Python, Prometheus Up & Running, MCP Spec 2026-07-28, OpenAI Agents SDK**

## 1. Fecho P0 — por que podemos avancar

| Prova | Estado |
|---|---|
| `python scripts/compute_readiness.py --json` 86.0/62.8/56.5 pesos soma 100 | PASS |
| `python scripts/verify_env.py` PASS secret 64 / db / grafana / service_role / dsn | PASS |
| `python scripts/setup.py --check` 9.6s + `docker compose config --quiet` OK | PASS |
| `reports/junit.xml` tests=5 failures=0 + `test_run_20260831_085856.md` 116.9s (9.5+9.2+59.6+14.2+24.3) | PASS |
| `acceptance_p0_to_p1.md` ASCII 0, 116.9s, 130 linhas | PASS |
| `.gitignore` .env.bak.* + timeout run_tests 25 + compute validacao fail-closed | PASS |

**5 READY (60 peso) + 3 PARTIAL (40*0.6=24) = 86. G1/G2/G3 PASS. P0 trancado.**

## 2. O que falta para comercializar — os 3 PARTIAL

| Dominio | Hoje | Para READY falta | CIPHER | Peso ganho |
|---|---|---|---|---|
| **Skills 15** | PARTIAL — notes OK, web_search sem key, calendar/email placeholder | OAuth Google Calendar+Gmail, token 0o700, refresh, web_search com Tavily + fallback, testes E2E | 001, 019 | +6.0 (15*0.4) |
| **Policy/HITL 10** | PARTIAL — engine enforce/audit, ApprovalManager TTL 1800s, mas sem rate-limit distribuido e HITL fora do loop | Rate-limit Redis distribuido, HITL polling integrado ao grafo, UI de aprovacao, audit_fallback.jsonl testado | 004, 018, 025 | +4.0 |
| **Infra/Observabilidade 10** | PARTIAL — compose+CI+junit OK, mas sem dashboards/alerts | 4 dashboards Grafana + 10 alerts Prometheus + metric jefrey_config_valid + runbooks | - | +4.0 |
| **Total** | | | | **+14.0 => 100% Impl** |

Projecao: Impl 86->100, Prod 62.8->73.0 (100*0.73), Comercial 56.5->65.7 (73*0.90). Com fator go-to-market P1 0.95 => **69.3%** (alvo 70%).

## 3. Principios (AXIOM = definicao de pronto)

Cada entrega P1 so e READY se tiver (SWE at Google + Pragmatic):
1. **Codigo** tipado (Ramalho TypedDict/Final/Literal) + sem BOM + py_compile OK
2. **Teste** reproduzivel (scripts/verify_p*.py + run_tests.py) + junit + sem flaky (timeout 25)
3. **Seguranca** fail-closed (Anderson) — CIPHER-002/019/001/004/018/025, chmod 0o600/0o700, mask SECRET_RE
4. **Observabilidade** (Kleppmann + Prometheus Up & Running) — metric + dashboard + alert + log estruturado
5. **Documentacao** — docs/JEFREY-AUDIT/*.md ASCII + tracer bullet + runbook
6. **Aceite** — gate binario reproduzivel em fresh machine

## 4. Epicos P1 — 8 frentes

### P1.1 OAuth Google (Skills) — 5 dias
- **Escopo**: Google Calendar (read/write) + Gmail (read/send) via google-api-python-client + google-auth-oauthlib, PKCE, scope minimo (calendar.events, gmail.send), consent screen, token em config/tokens/ 0o700, refresh automatico, revoke.
- **Arquivos**: src/jefrey/skills/calendar.py, email.py, src/jefrey/core/config.py (Integrations), scripts/setup.py (cria dir 0o700), .env.example (GOOGLE_CLIENT_ID/SECRET placeholder)
- **Seguranca**: CIPHER-001 service_role, nunca logar token (mask), state+nonce, .gitignore config/tokens/
- **Teste**: scripts/verify_p1.py ext + scripts/smoke_test.py (calendar/email SKIP sem credencial, PASS com mock), teste refresh expirado.
- **Obs**: metric jefrey_oauth_refresh_total, log audit
- **Aceite**: verify_p1 com cred mock PASS + token file 0o700 + docs/oauth.md

### P1.2 Skills hardening — 2 dias
- **web_search**: Tavily com fallback duckduckgo, cache 5min, timeout 10s, sem key -> SKIP nao FAIL (atual)
- **notes/automation**: ja READY, adicionar rate-limit por skill
- **Teste**: smoke >=3 skills, verify_p1 search ranking

### P1.3 Policy Engine distribuido — 3 dias
- **Rate-limit Redis**: janela deslizante (High Performance Python: SCAN vs KEYS ja OK), por user_id+tool, 60/min, 429 com Retry-After, fallback local se Redis down
- **RBAC**: matriz tool x role, enforce/audit/off, teste decide("save_note") vs "gmail_send" bloqueado sem OAuth
- **Arquivos**: src/jefrey/core/policy.py, redis_memory.py
- **Teste**: verify_p2.py Policy RBAC + rate-limit burst 70 req -> 10 bloqueados

### P1.4 HITL no loop — 3 dias
- **Integracao**: LangGraph node execute_tools -> se Policy==HITL -> ApprovalManager.create() -> wait_for_decision(TTL 1800s, poll 2s) -> resume/expired
- **UI**: endpoint /approvals (list/approve/reject) + n8n webhook opcional
- **Persistencia**: tabela approvals (ja existe models.py), audit_fallback.jsonl se DB down (CIPHER-025)
- **Teste**: verify_p2.py HITL create->approve->resume, expired TTL

### P1.5 Infra / Observabilidade — 4 dias
- **Dashboards Grafana (4)**: (1) Jefrey Health (config_valid, db+redis up), (2) Agent (tool latency p50/p95, errors), (3) Memory (pgvector QPS, hit rate), (4) Policy/HITL (approvals pendentes, rate-limit hits)
- **Alerts Prometheus (10)**: config_valid==0, pg_down, redis_down, tool_timeout>30s, hitl_expired_rate>5%, oauth_refresh_fail, disk>80%, etc
- **Metric**: jefrey_config_valid gauge (0/1) ja em verify_env, expor em /metrics
- **Arquivos**: docker/prometheus.yml, grafana/dashboards/*.json, src/jefrey/api/metrics.py
- **Aceite**: grafana:3000 dashboards importados + prometheus:9090 alerts firing test

### P1.6 UI Chat + Docs — 4 dias
- **UI**: web chat minimal (Next.js ou FastAPI Jinja) em ui/, thread_id, streaming, markdown, thread history via Postgres
- **Docs**: docs/runbook.md (fresh machine: setup --dev --non-interactive --force && docker compose up -d --wait && run_tests --ci), docs/security-audit/*
- **Aceite**: tracer bullet atualizado em README.md (ui:3001) + run_tests inclui ui health

### P1.7 Testes E2E + CI — 2 dias
- **Suite**: run_tests.py --ci 7 steps (add ui + oauth mock), --quick 3 steps, junit 7 tests, reports retencao 10 (rotacao)
- **CI**: .github/workflows/test.yml com services pgvector+redis, cache pip, setup --dev --force, run_tests --ci, upload junit
- **Paralelizacao opcional**: verify_p1 || verify_p2 (economia ~12s, mas manter sequencial por simplicidade Kleppmann single source)

### P1.8 Backup/Restore — 1 dia (paralelo)
- **Scripts**: scripts/backup.py (pg_dump + redis BGSAVE + tar data/), scripts/restore.py, cron n8n, teste restore em fresh DB

## 5. Ordem e dependencias (Kleppmann: ordem total)

Semana 1: P1.1 OAuth (desbloqueia Skills) -> P1.3 Rate-limit (usa Redis) -> P1.4 HITL (usa Policy)
Semana 2: P1.5 Observabilidade (paralelo) + P1.2 Skills hardening
Semana 3: P1.6 UI + P1.7 CI + P1.8 Backup
Gates: G1 P0-blocks 100% READY+PARTIAL (ja PASS), G2 suite 7 PASS, G3 infra OK + dashboards

## 6. Riscos e mitigacoes (Anderson)

| Risco | Mitigacao |
|---|---|
| Google OAuth consent bloqueado | Scope minimo + docs verificacao + mock sem credencial nao quebra CI |
| Redis rate-limit race | Lua script INCR+EXPIRE atomico (Kleppmann) |
| HITL deadlock (TTL nunca expira) | wait_for_decision com timeout + expired state + alert |
| Grafana sem dados | Provisioning automatico + fallback file datasource |

## 7. Checklist aceite P1 (gate P1->P2)

- [ ] compute_readiness 100/73/65.7 (Skills+Policy/HITL+Infra READY)
- [ ] verify_env PASS + verify_p1 (OAuth mock) PASS + verify_p2 (HITL+Policy) PASS
- [ ] run_tests --ci 7 PASS + junit failures 0 + compose OK + py_compile OK
- [ ] token file 0o600/0o700 + .env.bak ignorado + SECRET_RE mask
- [ ] Grafana 4 dashboards + Prometheus 10 alerts + /metrics jefrey_config_valid
- [ ] README tracer bullet + docs/runbook ASCII + acceptance_p1_to_p2.md

## 8. Estimativa

24 dias uteis (3 semanas) 1 dev senior, ou 2 semanas com 2 devs (P1.5/P1.1 paralelizaveis). Comercial 56.5% -> 69% (+12.5pp).

---
*Gerado 2026-08-31 — AXIOM/CIPHER — pronto para executar P1.1*
