# METRICS CARDINALITY — JEFREY (P5-01)
**Version:** 1.0 — 2026-09-02 — P5-01 Metrics Cardinality (Livro 4 cap5 + Axiom #4 + CIPHER-026/033)
**Gate:** `grep -rn 'labelnames.*user_id' src/` -> 0 + `curl -s /metrics | grep user_id` -> 0
**Base:** P4-FINAL 67fc89d (90/90 100%), PLANO_FASE_P5-01 1.0, SLO_RUNBOOK 1.1 FINAL

## Regra Axiomatica (Livro 4 cap5 + Axiom #4 Least Privilege)

> **Prometheus Up & Running 2nd — cap5 Cardinality (sec Label Cardinality, When to use labels):**
> Cada combinacao de labels gera uma serie distinta no TSDB. Cardinalidade = produto das cardinalidades de cada label.
> **Labels de ALTA cardinalidade (user_id, email, request_id, ip) MATAM o Prometheus** — TSDB explode (OOM), queries lentas, custo storage infinito.
> Solucao: user_id NUNCA vai para label. Vai para AuditLog (forense, Postgres) e Redis Streams topic `jefrey.events.{user_id}.{tool}` (isolamento Axiom #2), nunca para Prometheus.

**CIPHER-026** rate_limit e **CIPHER-033** kid rotation exigem `labelnames` sem `user_id`.
**CIPHER-010** audit separa forense (com user_id) de observabilidade (sem user_id).

## Inventario — 13 metricas (todas sem user_id)

Levantamento via `grep -rn 'Counter\|Gauge\|Histogram' src/jefrey/core/metrics.py` + `curl -s /metrics | grep "^jefrey_"`.

| # | Metrica | Tipo | Labels | Cardinalidade estimada | PromQL sem user_id | SLO / Alerta | Fonte |
|---|---------|------|--------|------------------------|---------------------|--------------|-------|
| 1 | `jefrey_config_valid` | Gauge | (none) | 1 | `jefrey_config_valid == 0` | JefreyConfigInvalid (1m, critical) | metrics.py CONFIG_VALID |
| 2 | `jefrey_rate_limit_total` | Counter | `tool_name`, `decision` (allow/deny/hitl) | ~40 tools * 3 = 120 | `sum(rate(jefrey_rate_limit_total{decision="deny"}[5m])) / clamp_min(sum(rate(jefrey_rate_limit_total[5m])),1) >0.001` | JefreyRateLimitDenialsHigh | metrics.py RATE_LIMIT_TOTAL — CIPHER-026 |
| 3 | `jefrey_eventbus_kid_legacy_total` | Counter | (none) — global | 1 | `increase(jefrey_eventbus_kid_legacy_total[10m]) >10` | JefreyKidLegacyHigh | metrics.py EVENTBUS_KID_LEGACY_TOTAL — CIPHER-033 / ADR-001 |
| 4 | `jefrey_memory_latency_seconds` | Histogram | `operation` (search/add), `le` | 2 * 6 buckets = 12 | `histogram_quantile(0.95, sum(rate(jefrey_memory_latency_seconds_bucket[5m])) by (le)) >0.3` | JefreyMemoryLatencyHigh (p95 300ms) | metrics.py MEMORY_LATENCY — Livro 4 cap6 |
| 5 | `jefrey_tools_blocked_total` | Counter | `tool_name`, `reason` | ~40*4=160 | `sum(rate(jefrey_tools_blocked_total[5m])) / clamp_min(sum(rate(jefrey_tool_exec_total[5m])),1) >0.01` | JefreyApiHighErrorRate | metrics.py |
| 6 | `jefrey_tool_exec_total` | Counter | `tool_name`, `status` (success/error) | ~40*2=80 | `sum(rate(jefrey_tool_exec_total[5m]))` | — | metrics.py |
| 7 | `jefrey_tool_exec_latency_seconds` | Histogram | `tool_name`, `le` | ~40*6=240 | `histogram_quantile(0.95, sum(rate(jefrey_tool_exec_latency_seconds_bucket[5m])) by (le))` | SLO 1.2 | metrics.py |
| 8 | `jefrey_policy_decisions_total` | Counter | `decision` (allow/deny/hitl), `tool_name` | ~3*40=120 | `sum(rate(jefrey_policy_decisions_total{decision="deny"}[5m]))` | — | metrics.py |
| 9 | `jefrey_audit_fallback_total` | Counter | (none) | 1 | `increase(jefrey_audit_fallback_total[5m]) >0` | — | metrics.py / audit.py CIPHER-025 |
| 10 | `jefrey_hmac_verify_failures_total` | Counter | `reason` (invalid_signature/expired/kid_legacy) | 3 | `sum(rate(jefrey_hmac_verify_failures_total[5m]))` | — | signing.py |
| 11 | `up` | Gauge | `job` (jefrey-api) | ~5 | `up{job="jefrey-api"} == 0` | JefreyServiceDown | prometheus scrape |
| 12 | `scrape_duration_seconds` | Gauge | `job` | ~5 | — | — | prometheus |
| 13 | `prometheus_build_info` | Gauge | — | 1 | — | — | prometheus |

**Total series estimado:** < 800 (sem user_id). **Com user_id (10k usuarios):** 800*10k = 8M series -> OOM (cap5). Por isso falha P8 se tiver user_id.

## Prova P5-01 (reproducao fail-closed)

```bash
# 1. Codigo sem user_id label (bloqueia regressao)
grep -rn 'labelnames.*user_id' src/  # -> 0 (deve ser 0)
grep -rn 'user_id.*label' src/       # -> 0
grep -rn 'Counter.*user_id' src/     # -> 0
grep -rn 'Histogram.*user_id' src/   # -> 0

# 2. /metrics sem user_id (via TestClient ou curl staging)
curl -s http://localhost:8000/metrics | grep jefrey_ | grep user_id  # -> 0 linhas
curl -s http://localhost:8000/metrics | grep "^jefrey_" | cut -d'{' -f1 | sort -u  # lista 13 sem user_id

# 3. Pytest 3 tests (SWE cap14)
python -m pytest tests/test_p5_metrics_cardinality.py -v  # 3 passed

# 4. Guard + CI
bash scripts/guard_anti_patterns.sh  # 6/6 PASS + EXTRA 0
```

## Grep de bloqueio (P5-01a)

- `scripts/guard_anti_patterns.sh` [EXTRA] ja verifica `user_id` label -> 0
- `.pre-commit-config.yaml` novo hook `metrics-no-user-id` -> bloqueia commit se regredir
- `.github/workflows/ci.yml` novo job `Metrics cardinality — no user_id label` -> bloqueia PR

## Referencias

- **Livro 4** Prometheus Up & Running 2nd — cap5 p.89-102 (Cardinality), cap6 Histograms, cap10 Alerting (for/labels), cap11 Grafana
- **Livro 6** SWE at Google — cap14 Testing (deterministic tests com monkeypatch)
- **Axiom** #4 Least Privilege + #2 Isolamento + #6 Persistencia Real
- **CIPHER** 026 (rate_limit), 033 (HMAC kid), 021 (silent except -> logger), 010 (audit separacao)
- **ADR-001** kid rotation dual-verify v1->v2, metric global sem label
