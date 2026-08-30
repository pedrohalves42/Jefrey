# 22 — P6: Observabilidade (Prometheus + Grafana)

**Data:** 2026-08-30
**Fase:** P6 — Observabilidade
**Status:** COMPLETA

---

## 1. Escopo

P6 implementa observabilidade completa para o Jefrey usando:
- **prometheus_client** (biblioteca oficial) — métricas manuais com controle total
- **Prometheus** (v2.53.0) — scrape, storage TSDB (30d), PromQL
- **Grafana** (v11.1.0) — dashboard 6 painéis, provisioning automático

## 2. Arquivos Criados/Modificados

### Novos (7 arquivos)
| Arquivo | Descrição |
|---------|-----------|
| `src/jefrey/core/metrics.py` | Módulo central — 12 objetos de métrica em 7 grupos |
| `src/jefrey/core/instrumentation.py` | Decorators `@timed` e `@counted` (sync + async) |
| `src/jefrey/api/metrics_endpoint.py` | Endpoint `GET /metrics` (Prometheus exposition format) |
| `docker/prometheus/prometheus.yml` | Config de scrape (jefrey-api:8000, 10s interval) |
| `docker/grafana/dashboards/jefrey.json` | Dashboard JSON com 6 painéis |
| `docker/grafana/provisioning/datasources/datasource.yml` | Auto-provisioning Prometheus datasource |
| `docker/grafana/provisioning/dashboards/dashboard.yml` | Auto-provisioning dashboard |
| `scripts/verify_p6.py` | Script de verificação — 26 checks |

### Modificados (5 arquivos)
| Arquivo | Mudança |
|---------|---------|
| `src/jefrey/core/executor.py` | Import TOOLS_BLOCKED, MCP_LATENCY; incrementa no deny; mede invoke |
| `src/jefrey/core/hitl.py` | Import APPROVALS_CREATED, APPROVALS_DECIDED; incrementa em create/decide |
| `src/jefrey/mcp/client.py` | Import MCP_CALLS, MCP_LATENCY; conta e mede em call_tool |
| `src/jefrey/core/pg_memory.py` | Import MEMORY_OPS, MEMORY_LATENCY; conta e mede em add/search |
| `src/jefrey/api/main.py` | Import e mount metrics_router; SERVICE_HEALTH.set(1) |
| `pyproject.toml` | +prometheus-client>=0.20.0 |
| `docker-compose.yml` | +prometheus +grafana services + volumes |

## 3. Métricas Implementadas

| Métrica | Tipo | Labels | Onde Instrumentado |
|---------|------|--------|-------------------|
| `jefrey_llm_latency_seconds` | Histogram | provider, model | (futuro: agent.py) |
| `jefrey_llm_tokens_total` | Counter | type, provider, model | (futuro: agent.py) |
| `jefrey_llm_cost_usd_total` | Counter | provider, model | (futuro: agent.py) |
| `jefrey_tools_blocked_total` | Counter | tool_name, reason | executor.py |
| `jefrey_approvals_created_total` | Counter | tool_name, risk_level | hitl.py |
| `jefrey_approvals_decided_total` | Counter | decision, tool_name | hitl.py |
| `jefrey_mcp_calls_total` | Counter | server, status | mcp/client.py |
| `jefrey_mcp_latency_seconds` | Histogram | server | mcp/client.py, executor.py |
| `jefrey_service_health` | Gauge | component | main.py |
| `jefrey_uptime_seconds` | Gauge | — | (reservado) |
| `jefrey_memory_ops_total` | Counter | operation, layer | pg_memory.py |
| `jefrey_memory_latency_seconds` | Histogram | operation, layer | pg_memory.py |

**Segurança:** Nenhuma métrica usa `user_id` como label (baixa cardinalidade).

## 4. Dashboard Grafana — 6 Paineis

| Painel | Tipo | Métrica(s) |
|--------|------|------------|
| LLM Latency (P50/P95/P99) | Time Series | `histogram_quantile(rate(jefrey_llm_latency_seconds_bucket))` |
| Tokens & Cost | Stat | `sum(increase(jefrey_llm_tokens_total[1h]))` |
| Service Health | Stat | `jefrey_service_health{component="api"}` |
| Tools Blocked | Bar Chart | `increase(jefrey_tools_blocked_total[1h])` |
| Approvals HITL | Bar Chart | `increase(jefrey_approvals_created_total/decided_total[1h])` |
| MCP Calls | Time Series | `rate(jefrey_mcp_calls_total)` + P95 latency |

## 5. Docker Compose — Servicos Adicionados

```yaml
prometheus:
  image: prom/prometheus:v2.53.0
  ports: ["9090:9090"]
  retention: 30d
  lifecycle API habilitado

grafana:
  image: grafana/grafana:11.1.0
  ports: ["3000:3000"]
  sign-up: desabilitado
  provisioning: automatico (datasource + dashboard)
```

## 6. Verificacao

`scripts/verify_p6.py` — **26/26 checks PASSED**

```
P06-01 a P06-10: metricas definidas
P06-11: instrumentation decorators
P06-12 a P06-13: endpoint + router
P06-14 a P06-17: instrumentacao nos 4 modulos
P06-18 a P06-24: docker infrastructure
P06-25: dependencia
P06-26: security (sem user_id labels)
```

## 7. Proximos Passos

- **P7:** Integration Testing & Verification (testes E2E com Prometheus real)
- **P8:** Docker Compose Production Stack (alertas, backup, monitoring do monitoring)
- **Futuro:** OpenTelemetry traces (P6+), Loki logs, Tempo traces

## 8. Padrao Seguido

- Commits detalhados com lista de fixes
- verify_pX.py com checks numerados (P06-NN)
- Security annotations em codigo (SECURITY, P6)
- Sem user_id em metricas (isolamento de dados)
- Nomes snake_case com unidades (_seconds, _total)
- Prefixo jefrey_ em todas as metricas
- Provisioning YAML do Grafana versionado
- Prometheus retention 30d
- Grafana sign-up desabilitado
