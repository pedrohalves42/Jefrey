# Runbook — Jefrey Operacoes

> Referencias: Google SWE (Site Reliability Engineering), Kleppmann DDIA Cap.12, Brazil Prometheus Up & Running, MCP Spec 2026-07-28

## 1. Restart
```bash
docker compose ps
docker compose restart jefrey-api mcp-server
docker compose logs -f jefrey-api --tail=200
curl -s http://localhost:8000/health | jq
curl -s http://localhost:8000/metrics | grep jefrey_config_valid
```
- SLO: p95 llm_latency <800ms, error_rate <1% — ver Grafana http://localhost:3000 (admin / GRAFANA_PASSWORD)

## 2. Rollback
```bash
git log --oneline -10
git revert <sha> --no-edit
docker compose build jefrey-api mcp-server
docker compose up -d
python scripts/verify_p7.py   # 54/54 deve passar
```

## 3. SLO Breach
| SLO | Expr | Acao |
|-----|------|------|
| ConfigInvalid | jefrey_config_valid==0 1m | checar .env JEFREY_API__SECRET_KEY hex32, HMAC, OAUTH AUD/ISS |
| HighErrorRate | rate(tools_blocked) >1% 5m | PolicyEngine / content_guard / rate_limit |
| RateLimitDeny | rate_limit deny >0.1% | JEFREY_MCP__TOOL_TIMEOUT / Redis password |
| Memory p95 >300ms | histogram_quantile 0.95 memory_latency | HNSW m=16 ef=64 -> ef 200 tuning docs/HNSW_TUNING.md |
| KidLegacy >10/10m | eventbus_kid_legacy_total | ADR-001 dual-verify v1/v2 rotation |
| STT p95 >2s | stt_duration bucket | faster-whisper small int8 cpu |

## 4. N8N Event Router
- Workflow: n8n/workflows/jefrey-event-router.json (versionado)
- Webhook: POST http://jefrey-n8n:5678/webhook/jefrey-events
- Import: n8n UI http://localhost:5678 -> Import from file -> Activate toggle (production URL)
- Teste: curl -X POST http://localhost:8000/connections/n8n/trigger -H "Authorization: Bearer <dev-token>" -H "X-User-Id: demo" -d '{"event_type":"tool_call","thread_id":"t1","payload":{"tool":"save_note","args":{"title":"x","content":"y"}}}'

## 5. Tenant Isolation (CIPHER-022, Anderson Cap.4)
- 6 camadas: auth middleware request.state.user_id -> pg_memory WHERE user_id -> Redis jefrey:wm:{user_id}:* -> audit_logs user_id -> approvals pending filter -> Checkpointer thread_id Namespaced
- Teste: user_A save_note, user_B search -> 0 rows (verify_p7 P07-004/005/008, test_p6_isolation.py)

## 6. Secrets Prod Hardening (SWE Cap.14)
```bash
openssl rand -hex 32  # JEFREY_API__SECRET_KEY
openssl rand -hex 32  # JEFREY_EVENTBUS__HMAC_KEY
# .env JEFREY_ENV=prod JEFREY_API__CORS_ORIGINS=https://seu-dominio.com JEFREY_REDIS__PASSWORD forte 32 chars
python scripts/verify_env.py --strict
```

## 7. CI/CD
- .github/workflows/ci.yml: compileall + pytest 40 + verify_p7 54 + guard + promtool check rules
- Gate: falha bloqueia merge (SWE Cap.9 CI/CD)

## 8. Referencias
1 Kleppmann DDIA, 2 Alto Building LLM Apps (6 memorias), 3 Ramalho Fluent Python, 4 OpenAI Agents SDK 0.22, 5 MCP Spec 2026-07-28 stateless, 6 Gorelick High Performance Python, 7 Hunt/Thomas Pragmatic Programmer, 8 Brazil Prometheus, 9 Anderson Security Engineering, 10 Google SWE
