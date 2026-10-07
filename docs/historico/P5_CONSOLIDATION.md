# P5 CONSOLIDATION — OBSERVABILITY FREEZE (P5-C) — 148/148

> **Version:** 1.0 — 2026-09-02 — P5-C 40m | **Base:** 687d589 (P6-gaps 148/148) | **Gates:** 148/148 100% WARNS0 BUGS0 | **Refs:** Axiom #1-7, CIPHER-021/025/026/028/033, Livro4 cap5/6/10/11, DDIA cap3, SWE cap14 | **Estado:** P5 DONE freeze, pronto para P6-C 150/150

## 1) Objetivo

Congelar P5.01..P5.06 sem regressao. Sai trancado com `verify_p6_data 19/19 2x`, `guard 6/6`, `grafana 8 panels`, `promtool 6/6`, `pytest 40 passed`, `deep 148/148`.

**P5-C != P6-C.** P5-C = observability freeze. P6-C = data verify 150/150 + CI gate + compose healthy (15m).

## 2) Matriz 6 Alerts x PromQL x for x slo x runbook

| # | Alert | PromQL (expr) | for | severity | slo | Runbook |
|---|-------|---------------|-----|----------|-----|---------|
| 1 | JefreyConfigInvalid | `jefrey_config_valid == 0` | 1m | critical | config | SLO_RUNBOOK 1.3: checar JEFREY_ENV, HMAC_KEYS_JSON, OAUTH AUD/ISS, REDIS_PASSWORD. Fail-closed ativo. |
| 2 | JefreyApiHighErrorRate | `sum(rate(jefrey_tools_blocked_total[5m])) / clamp_min(sum(rate(jefrey_tool_exec_latency_seconds_count[5m])),1) >0.01` | 5m | warning | error_rate | Ver PolicyEngine, guard, rate_limit. SLO 1.3 error_rate <1%. |
| 3 | JefreyRateLimitDenialsHigh | `sum(rate(jefrey_rate_limit_total{decision="deny"}[5m])) / clamp_min(sum(rate(jefrey_rate_limit_total[5m])),1) >0.001` | 5m | warning | rate_limit | Revisar rate_limit_max/window ou abuso por user_id/tool. |
| 4 | JefreyKidLegacyHigh | `increase(jefrey_eventbus_kid_legacy_total[10m]) >10` | 5m | warning | eventbus | ADR-001: rotacao HMAC dual-verify v1->v2, checar publish v2, metric global `labelnames=[]` 1 serie. |
| 5 | JefreyMemoryLatencyHigh | `histogram_quantile(0.95, sum(rate(jefrey_memory_latency_seconds_bucket[5m])) by (le)) >0.3` | 5m | warning | latency | docs/HNSW_TUNING.md ef_search 64 vs 200, pool_pre_ping/recycle, Seq Scan com 101 rows eh correto. |
| 6 | JefreyServiceDown | `up{job="jefrey-api"} == 0` | 1m | critical | availability | Checar `docker logs jefrey-api`, health /health, postgres/redis health. |

Prova: `docker/prometheus/alerts.yml` 67L 6 rules com `for`+`labels.severity`+`labels.slo`+`annotations.summary/description`.
Teste: `docker/prometheus/tests/alerts_test.yml` 4.3KB 6 groups `alert_rule_test` eval_time 4m/8m/14m -> `promtool test rules` SUCCESS 6/6 (promtool 2.53).
Drill: `scripts/drill_alerts.py` 126L Registry direto, dual sys.path, fail-closed RC2, 6 drills idempotentes 2x RC0.

## 3) Grafana 8 Panels SLO (Livro4 cap11)

**Arquivo:** `docker/grafana/dashboards/jefrey.json` `uid:jefrey-main` `editable:false` 8 panels | **Provisioning:** `datasources/datasource.yml` `orgId:1` `httpMethod:POST` | `dashboards/dashboard.yml` `editable:false` `allowUiUpdates:false` `updateIntervalSeconds:10` `path:/var/lib/grafana/dashboards:ro`

| # | Panel | PromQL | Tipo | SLO |
|---|-------|--------|------|-----|
| 1 | Config Valid | `jefrey_config_valid` | Stat | config |
| 2 | Service Up | `up{job="jefrey-api"}` | Stat | availability |
| 3 | Kid Legacy (10m) | `increase(jefrey_eventbus_kid_legacy_total[10m])` | TimeSeries | eventbus |
| 4 | API Error Rate (5m) | `sum(rate(jefrey_tools_blocked_total[5m])) / clamp_min(sum(rate(jefrey_tool_exec_latency_seconds_count[5m])),1)` | TimeSeries | error_rate |
| 5 | RateLimit Deny Rate (5m) | `sum(rate(jefrey_rate_limit_total{decision="deny"}[5m])) / clamp_min(sum(rate(jefrey_rate_limit_total[5m])),1)` | TimeSeries | rate_limit |
| 6 | Memory p95 Latency | `histogram_quantile(0.95, sum(rate(jefrey_memory_latency_seconds_bucket[5m])) by (le))` | TimeSeries | latency p95<300ms |
| 7 | Tools Blocked (1h) | `sum by (tool_name) (increase(jefrey_tools_blocked_total[1h]))` | Bar | error_rate |
| 8 | Approvals HITL (1h) | `sum by (tool_name, risk_level) (increase(jefrey_approvals_created_total[1h]))` | Bar | hitl |

Validacao: `python -m json.tool` OK + `grep '"editable": false'` + `grep 'by (le)'` + `grep 'orgId: 1'` + `bash scripts/guard_grafana.sh` RC0.

## 4) Metrics Cardinality <800 (Livro4 cap5, Axiom #2)

**Regra:** `user_id` NUNCA em `labelnames` (OOM 8M series com 10k usuarios vs <800 global). Vai para AuditLog (Postgres) e `jefrey.events.{user_id}.{tool}` (Redis Streams), nunca para Prometheus.

**Inventario 13 series (src/jefrey/core/metrics.py 18 metricas, todas sem user_id):**

| Metrica | Labels | Series est. |
|---------|--------|-------------|
| jefrey_config_valid | (none) | 1 |
| jefrey_rate_limit_total | tool_name,decision | 120 |
| jefrey_eventbus_kid_legacy_total | (none) global | 1 |
| jefrey_memory_latency_seconds | operation,le | 12 |
| jefrey_tools_blocked_total | tool_name,reason | 160 |
| jefrey_tool_exec_total | tool_name,status | 80 |
| jefrey_tool_exec_latency_seconds | tool_name,le | 240 |
| jefrey_policy_decisions_total | decision,tool_name | 120 |
| jefrey_audit_fallback_total | (none) | 1 |
| jefrey_hmac_verify_failures_total | reason | 3 |
| up | job | 5 |
| +2 prometheus internas | - | ~5 |
| **Total** | | **<800** |

Prova: `grep -rn 'labelnames.*user_id' src/` -> 0 + `EVENTBUS_KID_LEGACY_TOTAL labelnames=[]` + `docs/METRICS_CARDINALITY.md` 70L.
CI: `.pre-commit` hook `metrics-no-user-id` + `.github/workflows/ci.yml` job `REGISTRY no user_id` + `scripts/guard_anti_patterns.sh` EXTRA.

## 5) Drills idempotentes 2x

```bash
python scripts/drill_alerts.py && echo RC:$?  # 6/6 DONE
python scripts/drill_alerts.py && echo RC:$?  # idempotente 2x RC0
python scripts/drill_audit_fallback.py && echo RC:$?  # tmp_path isolado 3/3
python scripts/drill_audit_fallback.py && echo RC:$?  # 2x RC0
promtool check rules docker/prometheus/alerts.yml  # SUCCESS
promtool test rules docker/prometheus/tests/alerts_test.yml  # SUCCESS 6/6
```

## 6) Validacao P5-C (copiar e colar, ordem fixa)

```bash
python -m py_compile scripts/drill_alerts.py scripts/drill_audit_fallback.py scripts/verify_p6_data.py
python -m compileall -q src
bash scripts/guard_anti_patterns.sh  # 6/6 PASS exato
bash scripts/guard_grafana.sh  # 8 panels editable false by(le) orgId
python -m json.tool docker/grafana/dashboards/jefrey.json > /dev/null
python -c "import yaml,pathlib; [yaml.safe_load(pathlib.Path(p).read_text(encoding='utf-8')) for p in ['docker-compose.yml','.pre-commit-config.yaml','docker/prometheus/prometheus.yml','docker/prometheus/alerts.yml','docker/grafana/provisioning/datasources/datasource.yml','docker/grafana/provisioning/dashboards/dashboard.yml']]"
python -c "import re,pathlib; assert not __import__('re').search(r'labelnames.*user_id', pathlib.Path('src/jefrey/core/metrics.py').read_text())"
python scripts/verify_p6_data.py  # 19/19 2x
python scripts/verify_p6_data.py  # idempotente
python scripts/_validate_deep.py  # 148/148
python -m pytest tests -q  # 40 passed
promtool check rules docker/prometheus/alerts.yml
promtool test rules docker/prometheus/tests/alerts_test.yml  # 6/6
docker compose config -q  # com envs dummy prod
```

Esperado: `148/148 100% WARNS0 BUGS0`, `40 passed`, `6/6 SUCCESS`, `19/19 100% 2x`, `COMPOSE_OK`.

## 7) Referencias

- Livro4 Prometheus Up & Running 2nd cap5 (Cardinality), cap6 (Histograms by(le)), cap10 (Alerting), cap11 (Grafana)
- Livro6 SWE at Google cap14 Testing (monkeypatch deterministico)
- DDIA cap3 Persistence (dual-write audit)
- Axiom #1 FAIL-CLOSED, #2 ISOLAMENTO, #4 PERSISTENCIA REAL, #6 LEAST PRIVILEGE
- CIPHER-021 (no silent except), 025 (dual-write), 026 (rate_limit), 033 (kid rotation)
- ADR-001 kid rotation, THREAT_MODEL, SLO_RUNBOOK 1.3, docs/HNSW_TUNING.md

---
**Aceite P5-C:** 148/148 2x + guard 6/6 + cardinality 0 user_id + grafana 8 panels + alerts 6/6 + drills 2x + pytest 40 + reports 4 + git clean. Se qualquer NAO -> nao avanca P6-C.
