# Jefrey SLOs & Runbooks

**Status**: FINAL - P4 Prod Hardening  
**Related**: P4 Prod Hardening (SLOs CI/CD Prometheus, kid rotation, HNSW), P8 Roadmap  

---

## 1. Service Level Objectives

### 1.1. Availability SLOs

| SLO | Target | Window | Error Budget | Description |
|-----|--------|--------|--------------|-------------|
| **Availability** | 99.9% | Monthly | 43m 49s/month | Overall system availability (all services combined) |
| **MCP Server Uptime** | 99.95% | Monthly | 21m 50s/month | Jefrey MCP Gateway (port 8001) |
| **API Endpoint Uptime** | 99.9% | Monthly | 43m 49s/month | FastAPI endpoints (port 8000) |
| **OAuth2 Provider Uptime** | 99.9% (P3+) | Monthly | 43m 49s/month | OAuth2 introspection endpoint (P3 planned) |

### 1.2. Latency SLOs

| SLO | p95 Target | p99 Target | Description |
|-----|------------|------------|-------------|
| **API Response Latency** | 500ms | 2s | 95% of requests respond within 500ms; 99% within 2s |
| **Tool Execution Latency** | 2s | 10s | 95% of tool calls complete within 2s; 99% within 10s |
| **OAuth2 Token Introspection** | 200ms (P3+) | 500ms (P3+) | Token validation latency |
| **Memory Search Latency** | 300ms | 1s | pgvector/cos similarity search within memory layers |

### 1.3. Error Rate SLOs

| SLO | Target | Monthly Budget | Description |
|-----|--------|----------------|-------------|
| **Tool Error Rate** | < 1% | ~7h/month | Tool execution failures / total tool calls |
| **Auth Rejection Rate** | < 0.5% | ~3h/month | Token introspection denials / total auth attempts |
| **Approval HITL Rate** | 10-30% (expected) | N/A | Percentage of tool calls requiring HITL approval |
| **Rate Limit Denial Rate** | < 0.1% | ~5min/month | Requests denied by CIPHER-026 rate limiter |

### 1.4. Data Integrity SLOs

| SLO | Target | Description |
|-----|--------|-------------|
| **Memory Data Corruption** | 0 incidents/month | pgvector/Redis data integrity; dual-write audit consistency |
| **User ID Isolation** | 0 cross-user leaks/month | ChromaDB metadata isolation; user_id propagation verified |
| **Audit Log Completeness** | 100% | Every tool call must have audit log entry (Postgres + Redis dual-write) |

---

## 2. Service Level Indicators (SLIs)

### 2.1. Custom Prometheus Metrics

| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|-----------------|
| `APPROVALS_CREATED_total` | Counter | Total approvals created (HITL decisions) | N/A (monitor only) |
| `APPROVALS_APPROVED_total` | Counter | Approvals approved by user | N/A (monitor only) |
| `APPROVALS_DENIED_total` | Counter | Approvals denied by user | N/A (monitor only) |
| `TOOLS_EXECUTED_total` | Counter | Total tool executions | N/A (monitor only) |
| `TOOLS_BLOCKED_total` | Counter | Tools blocked by PolicyEngine/RBAC | > 2σ above baseline → investigate |
| `TOOLS_RATE_LIMITED_total` | Counter | Tools rate-limited (CIPHER-026) | > 0.1% of total calls → review rate limits |
| `AUTH_TOKENS_INTSPECTED_total` | Counter | OAuth2 token introspections (P3+) | N/A (monitor only) |
| `AUTH_TOKENS_DENIED_total` | Counter | OAuth2 token introspection denials (P3+) | > 0.5% → investigate auth |
| `CONTENT_GUARD_TOTAL` | Counter | Content guard pattern matches | Spikes investigate for false positives/negatives |
| `MCP_MESSAGE_SIGNED_total` | Counter | MCP messages with HMAC signature (CIPHER-033, P3+) | N/A (monitor only) |
| `MCP_MESSAGE_UNSIGNED_total` | Counter | MCP messages without signature (CIPHER-033, P3+) | Investigate if > 0 after P3 deployment |

### 2.2. Health Check Endpoints

| Endpoint | Description | Expected Response |
|----------|-------------|-------------------|
| `GET /health` | Comprehensive infrastructure status | `200 OK` with json: `{status: "healthy", mcp: {...}, postgres: ..., redis: ..., policy: ..., tools: ...}` |
| `GET /ready` | Readiness for request processing | `200 OK` if all dependent services available |
| `GET /metrics` | Prometheus metrics endpoint | Text format exposable by prometheus |

---

## 3. Runbooks

### 3.1. Redis Availability Degradation

**Symptoms**:
- `REDIS_UP` health check returns `false`
- `RATE_LIMIT_DENY_total` spikes (rate limiter falling back)
- `APPROVALS_CREATED_total` slowdown (approvals stored in Redis)

**Steps**:
1. Check Docker container: `docker ps | grep jefrey-redis`
2. Check Redis logs: `docker logs jefrey-redis`
3. Verify requirepass: `redis-cli -a "$JEFREY_DATABASE__PASSWORD" ping`
4. If Redis is down, restart: `docker restart jefrey-redis`
5. If data loss suspected, restore from Postgres backup (audal dual-write)
6. Verify rate limiter recovery: monitor `RATE_LIMIT_DENY_total` returns to baseline
7. Post-incident: review if single-point-of-failure; consider Redis replica

**Rollback**:  
- All tool execution falls back to Postgres-only mode (slower but functional)  
- Audit log entries continue in Postgres (dual-write ensures completeness)  
- No data loss if Postgres audit was writing concurrently

---

### 3.2. OAuth2 Provider Issues (P3+)

**Symptoms**:
- `AUTH_TOKENS_DENIED_total` spikes
- `AUTH_TOKENS_INTSPECTED_total` = 0 (provider not running)
- Clients report "invalid_token" or "access_denied"

**Steps**:
1. Check OAuth2 provider process: `docker ps | grep jefrey-oauth2`
2. Check JWKS endpoint: `curl http://localhost:8001/oauth/.well-known/jwks.json`
3. Verify token signing key rotation: check `JEFREY_OAUTH2_KEY_ROTATION_DAYS` env var
4. If key rotation issue: generate new JWKS, update `JEFREY_OAUTH2_PUBLIC_KEY` secret
5. Rotate tokens if compromise suspected: invalidate all active sessions in Postgres
6. Restart OAuth2 provider: `docker restart jefrey-oauth2`
7. Post-incident: review access logs for anomalous token usage

**Rollback**:  
- Disable OAuth2 introspection; fall back to pre-P3 Bearer token validation (hmac.compare_digest on secret_key)  
- All other functionality continues unaffected (OAuth2 is additive in P3)

---

### 3.3. Tool Execution Failures

**Symptoms**:
- `TOOLS_EXECUTED_total` not incrementing for specific tool
- `TOOLS_BLOCKED_total` increments for previously working tool
- User reports "tool unavailable" or "permission denied"

**Steps**:
1. Check PolicyEngine decision: review recent `APPROVALS_CREATED_total` entries
2. Verify tool is registered in ToolRegistry: `python -c "from src.jefrey.core.registry import TOOL_REGISTRY; print(TOOL_REGISTRY.registered_names())"`
3. Check tool risk/role matches user's role: consult RBAC engine
4. Check CIPHER-026 rate limiter: `RATE_LIMIT_DENY_total` for this user/tool combo
5. Check content guard: `CONTENT_GUARD_TOTAL` may have triggered on output
6. Inspect recent audit log entries in Postgres `approvals` table
7. If tool was recently modified, check if registration was updated (`register_default_tools()`)

**Rollback**:  
- If new tool registration caused blockage: re-run `register_default_tools()` with correct risk/role  
- If PolicyEngine decision changed: review `decide()` method risk_of() logic  
- If rate limiter changed: adjust `RATE_LIMIT` env var or `RateLimiter` configuration

---

### 3.4. User ID Isolation Leak

**Symptoms**:
- `user_id` appears in another user's ChromaDB search results
- `CONTENT_GUARD_TOTAL` has unusual pattern matches
- Audit log shows `user_id` mismatch across tool executions

**Steps**:
1. Verify `user_id` is in stream config: check `src/jefrey/core/agent.py` `stream()` method
2. Verify `save_important_memory()` passes `user_id`: check `src/jefrey/core/memory.py`
3. Check ChromaDB metadata filter: ensure `metadata={"user_id": user_id}` in all search/get/delete calls
4. Verify no hardcoded `user_id` values in codebase (search for `user_id="default"` or similar)
5. Run user isolation test: execute as different users and verify ChromaDB results are separate
6. If leak found: fix the code path, re-sync ChromaDB data if needed

**Rollback**:  
- Temporarily disable user_id propagation (revert to no isolation)  
- All users share same memory space (less secure but functional)  
- Post-incident: re-enable isolation after fix validated

---

### 3.5. Prometheus Metrics Reset

**Symptoms**:
- Grafana dashboards showing flatlines or strange values
- Alertmanager firing false positives
- `compute_readiness.py` showing incorrect percentages

**Steps**:
1. Check if Prometheus was restarted or config changed
2. Delete Prometheus local storage if corrupted: `rm -rf /prometheus/data/`
3. Restart Prometheus: `docker restart jefrey-prometheus`
4. Allow 5-10 minutes for metrics to re-accumulate
5. Verify `compute_readiness.py` re-runs correctly
6. If metrics still incorrect, check `prometheus.yml` target configurations

**Rollback**:  
- Manual metric values can be estimated from application logs  
- No data loss since metrics are cumulative counters  
- Application functionality unaffected; only monitoring visibility

---

## 4. Error Budget Policy

### 4.1. Budget Thresholds

| Budget | Action | Owner | Timeline |
|--------|--------|-------|----------|
| **> 50% consumed** | Alert team lead, plan remediation | Team lead | Within 48h |
| **> 75% consumed** | Escalate to DevOps, consider feature freeze | DevOps lead | Within 24h |
| **> 90% consumed** | Emergency meeting, mandatory remediation sprint | Project maintainer | Immediate |
| **100% consumed** | Circuit breakers enabled, degraded mode | Project maintainer | Immediate |

### 4.2. Remediation Priority

| Priority | Condition | Action | Max Time |
|----------|-----------|--------|----------|
| **P0** | Error budget > 90% OR critical SLO breach | Stop non-feature work; fix immediately | 4h |
| **P1** | Error budget > 75% OR significant SLO drift | Plan sprint; fix within sprint | 1 week |
| **P2** | Error budget > 50% OR minor SLO drift | Add to backlog; fix within 2 weeks | 2 weeks |
| **P3** | Error budget < 50% OR no SLO impact | Deferred to next quarter | Next quarter |

### 4.3. When Budget is Exhausted

1. **Enable circuit breakers** - disable non-essential features to conserve budget
2. **Enter degraded mode** - functionality continues at reduced capacity/quality
3. **Communicate with stakeholders** - notify users of reduced capabilities
4. **Focus on remediation** - all hands on budget-recovering fixes only
5. **Post-incident review** - document root cause, prevent recurrence

---

## 5. CI/CD & Deployment SLOs

| Metric | Target | Description |
|--------|--------|-------------|
| **Deployment Frequency** | ≥ 1/ sprint | Minimum acceptable for agile development |
| **Lead Time for Changes** | ≤ 1 week | From commit to production deploy |
| **Change Failure Rate** | ≤ 10% | Deployments causing SLO breach or rollback |
| **Mean Time to Restore** | ≤ 30 min | From incident detection to full recovery |
| **Prometheus Deployment** | Canary 10% → 100% | New Prometheus config rolled incrementally |

---

## 5.1 Alerts (P4-04)

| Alert | Expr | SLO |
|-------|------|-----|
| JefreyConfigInvalid | jefrey_config_valid==0 | config |
| JefreyApiHighErrorRate | blocked/tool_exec >1% | error_rate |
| JefreyRateLimitDenialsHigh | deny/total >0.1% | rate_limit |
| JefreyKidLegacyHigh | increase(kid_legacy[10m])>10 | eventbus |
| JefreyMemoryLatencyHigh | p95 memory >300ms | latency |
| JefreyServiceDown | up==0 | availability |

Regras em `docker/prometheus/alerts.yml`, carregadas via `rule_files` em `docker/prometheus/prometheus.yml`. CI roda `guard + audit prod + pytest -q + compose config -q` em `.github/workflows/ci.yml`.

---

## 6. Related Documentation

- `THREAT_MODEL.md` - Security assumptions and controls
- `P3_PLAN.md` - P3 objectives including CIPHER-031/032/033
- `P2_VALIDATION_REPORT.md` - P2 validation results
- `compute_readiness.py` - Implementation/production/commercial readiness
- `src/jefrey/core/policy.py` - PolicyEngine (HITL, risk assessment)
- `src/jefrey/core/rate_limit.py` - Redis token bucket (CIPHER-026)

---

**Document Version**: 1.1  
**Last Updated**: 2026-09-02  
**Next Review**: P4 post-merge review  
**Owner**: Project maintainer