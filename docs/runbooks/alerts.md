# Runbooks — Jefrey Alertas Prometheus (P6 Observabilidade)

Gerado em 2026-09-11 — Passo 3 P2 Comercial 90%->100%. Mapeia os 7 alerts de docker/prometheus/alerts.yml (grupo jefrey.slo, interval 30s).

Referencias: Security Engineering (Ross Anderson cap. 8), Prometheus Up & Running, Kleppmann DDIA cap.12.

## Como usar
1. Grafana http://localhost:3000 (admin/mudar_senha_grafana) -> Explore -> jefrey_*
2. curl -s http://localhost:8000/metrics | grep jefrey_
3. docker logs jefrey-api --tail 100 / docker inspect jefrey-api --format "{{.State.Health.Status}}"

---

### 1. JefreyConfigInvalid jefrey_config_valid == 0 for 1m severity: critical
SLO: jefrey_config_valid deve ser 1.0 em DEV e PROD (CIPHER-019/002/001).
Sintoma: Producao cai para 73% (fator 0.73). Main.py CONFIG_VALID.set(0) quando secret_key <32 ou CHANGE_ME ou password==jefrey && is_prod ou service_role not in allowed_roles.
Diagnostico: curl -s localhost:8000/metrics | grep jefrey_config_valid ; docker inspect jefrey-api --format "{{range .Config.Env}}{{println .}}{{end}}" | findstr JEFREY
Mitigacao: Corrigir .env (gerar python -c "import secrets;print(secrets.token_hex(32))" para JEFREY_API__SECRET_KEY e JEFREY_EVENTBUS__HMAC_KEY), docker compose up -d jefrey-api (volume ro reflete host, sem rebuild). Verificado 2026-09-11: patch cfg.is_prod fez 0.0->1.0.
Rollback: git show HEAD:src/jefrey/api/main.py | grep CONFIG_VALID

### 2. ApiHighErrorRate rate(jefrey_tools_blocked_total[5m]) > 0.1 for 1m severity: warning
SLO: p95 tool exec <300ms, taxa de bloqueio <10%.
Diagnostico: curl -s localhost:8000/metrics | grep jefrey_tools_blocked ; docker logs jefrey-api | findstr TOOLS_BLOCKED
Mitigacao: Revisar src/jefrey/core/policy.py (RiskLevel HIGH autonomous deny), src/jefrey/core/registry.py (R.LOW/MEDIUM/HIGH). Whitelist via allowed_roles.
Runbook: python scripts/verify_p7.py deve manter P07-048/049 PASS.

### 3. RateLimitDenialsHigh rate(jefrey_rate_limit_total{decision="deny"}[5m]) > 5 for 5m severity: warning
Diagnostico: curl -s localhost:8000/metrics | grep jefrey_rate_limit
Mitigacao: src/jefrey/core/rate_limit.py RateLimiter Redis token bucket (incr+expire+ttl pipeline atomic, fail-closed). Ajustar policy.rate_limit_max / rate_limit_window em config.py.

### 4. KidLegacyHigh increase(jefrey_eventbus_kid_legacy_total[10m]) > 0 for 1m severity: warning
SLO: kid rotation v1/v2 dual-verify sem legacy.
Diagnostico: curl -s localhost:8000/metrics | grep kid_legacy ; findstr kid src/jefrey/eventbus/signing.py
Mitigacao: EventBus HMAC JEFREY_EVENTBUS__HMAC_KEYS_JSON com keys v1/v2 + HMAC_KID=v1. EVENTBUS_KID_LEGACY_TOTAL deve permanecer 0.0.

### 5. MemoryLatencyHigh histogram_quantile(0.95, jefrey_memory_latency_seconds) > 0.5 for 5m severity: warning
SLO: p95 memory <500ms.
Diagnostico: curl -s localhost:8000/metrics | grep jefrey_memory_latency
Mitigacao: Revisar pg_memory.py (HNSW m=16 ef=64 vector_cosine_ops), models.py indexes CONCURRENTLY, db.py pool_pre_ping+recycle 3600. Ver docs/HNSW_TUNING.md bench ef 64 vs 200.

### 6. ServiceDown jefrey_service_health{component="api"} == 0 for 1m severity: critical
SLO: disponibilidade 99.9% (43m downtime/mes).
Diagnostico: curl -s localhost:8000/health ; curl -s localhost:8001/health (mcp 17 tools) ; docker ps --format "table {{.Names}} {{.Status}}" ; docker inspect jefrey-api --format "{{json .State.Health}}"
Mitigacao: docker compose up -d --wait — deve resultar 8/8 healthy (postgres, redis, api, mcp, n8n, prometheus, grafana, frontend). Frontend python -m http.server 8080 em frontend/Dockerfile.frontend (nao uvicorn main:app).
Escalada: Se jefrey-api Unhealthy repetir ImportError RedisWorkingMemory, verificar alias class RedisWorkingMemory(RedisShortTermMemory) em src/jefrey/core/redis_memory.py.

### 7. SttLatencyHigh histogram_quantile(0.95, jefrey_stt_duration_seconds) > 2.0 for 5m severity: warning
SLO: p95 STT <2s.
Diagnostico: curl -s localhost:8000/metrics | grep stt_duration
Mitigacao: Verificar src/jefrey/api/stt.py provider whisper/pyttsx3, voice STT/TTS settings em config.py.

---
Checklist pos-incidente: python scripts/verify_p7.py (54/54) + verify_p6.py (27/27) + verify_cipher_fixes.py (32/32) + verify_p6_data.py (23/23) + curl /metrics | grep jefrey_config_valid (1.0) + python scripts/compute_readiness.py --json (100/100/100).