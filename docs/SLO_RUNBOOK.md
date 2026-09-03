# SLO RUNBOOK — Jefrey v1.0.0 (P8)

**Status**: FINAL — P8 TAG v1.0.0 2026-09-03
**Refs**: Livro4 Prometheus Up & Running 2nd cap10 Alerting + cap11 Grafana + DDIA cap6/12 + SWE cap14
**Relacionado**: docker/prometheus/alerts.yml (6 alerts), docker/prometheus/prometheus.yml, docker/grafana/dashboards/jefrey.json (8 panels), docs/P5_CONSOLIDATION.md, docs/HNSW_TUNING.md

## 1) SLOs (SLO_RUNBOOK 1.3)

| SLO | SLI | Alvo | Janela | Alert |
|-----|-----|------|--------|-------|
| Availability | up{jefrey-api}==1 | 99.9% | 1m | JefreyServiceDown for 1m critical slo:availability |
| Config Valid | jefrey_config_valid==1 | 100% | 1m | JefreyConfigInvalid for 1m critical slo:config |
| Error Rate | tools_blocked / tool_exec | <1% | 5m | JefreyApiHighErrorRate for 5m warning slo:error_rate |
| RateLimit | rate_limit deny / total | <0.1% | 5m | JefreyRateLimitDenialsHigh for 5m warning slo:rate_limit |
| EventBus Legacy | increase(kid_legacy[10m]) | <10/10m | 10m | JefreyKidLegacyHigh for 5m warning slo:eventbus |
| Latency p95 | histogram_quantile 0.95 by(le) | <300ms | 5m | JefreyMemoryLatencyHigh for 5m warning slo:latency |

## 2) Matriz 6 alerts — PromQL × for × slo × runbook

| Alert | PromQL | for | severity | slo | Runbook |
|-------|--------|-----|----------|-----|---------|
| JefreyConfigInvalid | jefrey_config_valid==0 | 1m | critical | config | checar JEFREY_ENV, HMAC_KEYS_JSON, OAUTH AUD/ISS, REDIS_PASSWORD; fail-closed ativo; `docker logs jefrey-api` |
| JefreyServiceDown | up{job="jefrey-api"}==0 | 1m | critical | availability | `docker ps` + `docker logs jefrey-api --tail 50` + `curl localhost:8000/health` + checar postgres/redis health |
| JefreyApiHighErrorRate | sum(rate(tools_blocked[5m]))/clamp_min(sum(rate(tool_exec_count[5m])),1)>0.01 | 5m | warning | error_rate | ver PolicyEngine guest/user/admin, guard_anti_patterns, rate_limit |
| JefreyRateLimitDenialsHigh | sum(rate(rate_limit{decision="deny"}[5m]))/clamp_min(sum(rate(rate_limit[5m])),1)>0.001 | 5m | warning | rate_limit | revisar JEFREY_RATE_LIMIT__MAX/WINDOW ou abuso por tool_name |
| JefreyKidLegacyHigh | increase(kid_legacy[10m])>10 | 5m | warning | eventbus | rotacao incompleta; ver ADR-001 dual-verify v1->v2, `HMAC_KID=v2` |
| JefreyMemoryLatencyHigh | histogram_quantile(0.95,sum(rate(memory_latency_bucket[5m])) by(le))>0.3 | 5m | warning | latency | ver docs/HNSW_TUNING.md ef 64 vs 200, pool_pre_ping 3600, `EXPLAIN` Seq Scan vs Index Scan |

## 3) Dashboards (8 panels — jefrey-main)

| Panel | PromQL | Painel |
|-------|--------|--------|
| Config Valid | jefrey_config_valid | Stat |
| Service Up | up{jefrey-api} | Stat |
| Kid Legacy 10m | increase(kid_legacy[10m]) | TimeSeries |
| API Error Rate 5m | sum(rate(tools_blocked[5m]))/… | TimeSeries |
| RateLimit Deny 5m | sum(rate(rate_limit{deny}[5m]))/… | TimeSeries |
| Memory p95 | histogram_quantile(0.95,sum(rate(bucket[5m])) by(le)) | TimeSeries |
| Tools Blocked 1h | sum by(tool_name)(increase(tools_blocked[1h])) | Bar |
| Approvals HITL 1h | sum by(tool_name,risk_level)(increase(approvals[1h])) | Bar |

Todos usam `by (le)` com espaco (Livro4 cap6) e `editable:false` (Axiom #4).

## 4) Operacao

- **Regra Prometheus**: `rule_files: /etc/prometheus/alerts.yml` em prometheus.yml (cap10).
- **Testes**: `docker/prometheus/tests/alerts_test.yml` 6 grupos interval 1m eval_time 4m/8m/14m — `promtool test rules` SUCCESS.
- **Cardinality**: <800 series global, sem user_id label (Livro4 cap5) — `EVENTBUS_KID_LEGACY_TOTAL labelnames=[]` + `RATE_LIMIT_TOTAL [tool_name,decision]`.
- **Compose healthy**: `docker compose config -q` RC0 com 8 envs ?required fail-closed (DDIA cap6).
- **Incidentes**: abrir issue com label slo:xxx + anexar `reports/p6-*.log` + `docker logs`.

## 5) Checklist P8

- [x] alerts.yml 6 alerts for/severity/slo + promtool check/test SUCCESS
- [x] grafana jefrey.json 8 panels by(le):2 editable:false orgId:1
- [x] compose healthy 7/7 api/mcp/redis/postgres/prometheus/grafana/n8n
- [x] verify 21/21 2x + deep 150/150 + pytest 40 passed


## Appendix P5-04 — Drill e Validacao (promtool 2.53, Livro4 cap10)

- **P5-04** alerts_test.yml 6 groups OK (JefreyConfigInvalid, JefreyApiHighErrorRate, JefreyRateLimitDenialsHigh, JefreyKidLegacyHigh, JefreyMemoryLatencyHigh, JefreyServiceDown)
- promtool check rules + test rules OK (docker/prometheus/tests/alerts_test.yml)
- drill_alerts.py FAIL-CLOSED JEFREY_ENV gate + py_compile OK + no user_id label
- Grafana jefrey.json 8 panels + datasource orgId:1 OK (Livro4 cap11)
