# SLOs Formais — Jefrey AI Infrastructure (P2 Comercial 100%)

Versao: 1.0.0 — 2026-09-11 | Dono: SRE Jefrey | Revisao trimestral
Referencias: Site Reliability Engineering (Google), DDIA Kleppmann cap.12, Prometheus Up & Running.

## 1. Definicoes

| SLI | SLO | Janela | Error Budget | Fonte |
|-----|-----|--------|-------------|-------|
| Disponibilidade API jefrey_service_health{api}==1 | 99.9% (43m20s/mes) | 30d rolling | 0.1% | GET /health, blackbox docker inspect Health.Status |
| Latencia Tool p95 histogram_quantile(0.95, jefrey_tool_exec_latency_seconds) | <300ms | 5m | 5% >300ms dispara warning | TOOL_EXEC_LATENCY histogram buckets 0.01..10s |
| Latencia Memory p95 histogram_quantile(0.95, jefrey_memory_latency_seconds) | <500ms | 5m | 5% >500ms dispara warning | MEMORY_LATENCY |
| Latencia STT p95 histogram_quantile(0.95, jefrey_stt_duration_seconds) | <2.0s | 5m | 5% >2s dispara warning | STT_DURATION |
| Config Valida jefrey_config_valid | 1.0 (100%) | 1m | 0 — qualquer 0.0 e critical | main.py CONFIG_VALID.set CIPHER-019 |
| Taxa de bloqueio rate(jefrey_tools_blocked_total[5m]) | <0.1/s | 5m | — | PolicyEngine |
| Kid legacy increase(jefrey_eventbus_kid_legacy_total[10m]) | 0 | 10m | 0 | EventBus signing kid v1/v2 |

## 2. Error Budget Policy

- 99.9% disponivel: 43m downtime/mes. Se budget queimar >50% em 7d -> freeze de features, foco em estabilidade.
- Burn rate alerts: ApiHighErrorRate (warning 1m) e ServiceDown (critical 1m) em docker/prometheus/alerts.yml com for: 1m/5m e labels: {severity, slo}.
- Janela de avaliacao: Prometheus retention 30d (docker/prometheus/prometheus.yml).

## 3. Instrumentacao (P6)

- 18 metricas jefrey_* sem label user_id (cardinalidade <800, ver test_p5_metrics_cardinality.py).
- 7 alerts jefrey.slo interval 30s for 1m/5m severity/slo + rule_files: [/etc/prometheus/alerts.yml].
- 9 panels Grafana docker/grafana/dashboards/jefrey.json (editable:false, datasource PBFA97CFB590B2093 prometheus:9090): Config Valid, Service Up, Kid Legacy (10m), API Error Rate, RateLimit Deny Rate, Memory p95, Tools Blocked, Approvals HITL, STT Latency.
- Validacao: promtool check rules docker/prometheus/alerts.yml && promtool check config docker/prometheus/prometheus.yml + Grafana lint + python scripts/verify_p6.py 27/27 + verify_p6_data.py 23/23.

## 4. Operacao

### Health Drill (executar pos-deploy)
docker ps --format "table {{.Names}} {{.Status}}"
curl -s http://localhost:8000/health          # {status:ok,version:0.1.0}
curl -s http://localhost:8001/health          # {mcp:ok,policy:{mode:enforce},tools:17}
curl -s http://localhost:3001/ | grep ws://localhost:8000/ws  # frontend 3D
curl -s http://localhost:8000/metrics | grep jefrey_config_valid # 1.0
curl -s http://localhost:8000/metrics | grep jefrey_service_health # 1.0
python scripts/verify_p7.py    # 54/54 ALL PASS
python scripts/verify_p6.py    # 27/27 ALL PASS
python scripts/verify_cipher_fixes.py # 32/32
python scripts/compute_readiness.py --json # 100/100/100 fator 1.0

### Backup/Restore (DDIA cap.3 — prova idempotente)
Ver scripts/backup_restore.sh. Prova: pg_dump -U jefrey -d jefrey | psql -U jefrey -d jefrey_restore RC 0, re-execucao idempotente, verificado em verify_p6_data.py gate backup pg_dump RC0 prove OK.

## 5. Dependencias

- Postgres 16 + pgvector HNSW m=16 ef_construction=64 vector_cosine_ops, pool_pre_ping + pool_recycle 3600
- Redis 7.2 jefrey:wm:{user_id}:* ex=86400 DLQ 5000
- Docker Compose 8 servicos (postgres, redis, api:8000, mcp:8001 streamable-http, n8n:5678, prometheus:9090 retention 30d, grafana:3000, frontend:3001:8080)
- MCP Gateway streamable-http 8001 /health stateless_http=True

## 6. Contato

On-call via n8n webhook (jefrey-n8n:5678) -> hitl_notify.py (notify_pending_approval). Runbooks em docs/runbooks/alerts.md.