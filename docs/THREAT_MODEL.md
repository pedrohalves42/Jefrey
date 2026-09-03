# THREAT MODEL — Jefrey v1.0.0 (P8)

**Status**: FINAL — P8 TAG v1.0.0 2026-09-03
**Refs**: Livro3 Security Engineering Ross Anderson 3rd ed ch.4 + Axiom #1-7 (6 FAIL-CLOSED) + CIPHER 021/025/026/031/032/033/035 + DDIA cap6 + SWE cap14
**Relacionado**: ADR-001 kid rotation, docs/JEFREY-AUDIT, audit_pessimista.py

## 1) Ativos

| Ativo | Local | Protecao |
|-------|-------|----------|
| user_id isolamento | pg_memory _build_filter + PolicyContext + topic per-tenant + DLQ per-tenant | Axiom #2 |
| HMAC EventBus | JEFREY_EVENTBUS__HMAC_KEYS_JSON v1/v2 + kid + dual-verify + compare_digest + canonical sort_keys | CIPHER-033, ADR-001 |
| JWKS / Token | RS256 + kid + aud/iss/exp + urlsafe_b64encode sem padding + TTL 24h + sismember revoked | Axiom #5, CIPHER-031/035 |
| Skill Risk | overwrite=False + load_skills() + PolicyEngine RBAC guest/user/admin + HITL UNKNOWN deny | CIPHER-032, Axiom #6 |
| Observabilidade | 18 metrics <800 series sem user_id + 6 alerts + 8 panels editable:false | Livro4 cap5/6/10/11 |

## 2) Superficies

| Superficie | Vetor | Controle |
|------------|-------|----------|
| API :8000 /chat /memory /approvals /health | HTTP + JWT + rate_limit pipeline incr/expire fail-closed | CIPHER-026, Axiom #4 |
| MCP :8001 streamable-http | MCP 2.x + PolicyEngine per-tool + RateLimiter deny | CIPHER-032 |
| EventBus Redis Streams | XADD maxlen10000 approximate per-tenant + XREADGROUP + XACK + DLQ maxlen5000 | CIPHER-033 |
| n8n :5678 | Workflow versionado + HMAC kid rotation | CIPHER-033 |
| Prometheus :9090 / Grafana :3000 | Metrics sem PII + redact_pii 2 camadas | CIPHER-025 |

## 3) Ameacas e Controles (STRIDE)

| ID | Ameaca | Impacto | Controle | Prova |
|----|--------|---------|----------|-------|
| T1 | Tenant escape via memory | Alto | _build_filter user_id mandatory + topic jefrey.events.{user_id}.{tool} + DLQ jefrey:dlq:{user_id} + tests/test_p6_isolation 2/2 | Axiom #2 |
| T2 | Replay EventBus | Alto | HMAC user_id.timestamp.canonical + kid v1/v2 dual-verify + DeprecationWarning v0 + EVENTBUS_KID_LEGACY_TOTAL [] | ADR-001 |
| T3 | Token forjado | Alto | urlsafe_b64encode sem padding + RS256+kid + aud/iss/exp/kid/alg + compare_digest + JWKS TTL 24h + sismember revoked | Axiom #5 |
| T4 | Credencial em prod | Alto | JEFREY_ENV Literal dev/prod + validate_for_production() 8 envs ?required fail-closed + env_prefix JEFREY_ | Axiom #6 |
| T5 | Silent except oculta falha | Medio | guard_anti_patterns 6 greps (except: pass -> logger) + audit_pessimista RC1 | CIPHER-021 |
| T6 | Cardinality OOM | Medio | labels [] e [tool_name,decision] <800 series, nunca user_id | Livro4 cap5 |
| T7 | CORS wildcards | Medio | allow_credentials False + enumerated CORS origins/methods/headers | Axiom #6 |

## 4) Controles por Axiom

- **FAIL-CLOSED** deny/false/raise: PolicyEngine UNKNOWN deny + rate_limit fail-closed + signing RuntimeError prod
- **ISOLAMENTO** user_id=None guest + _build_filter mandatory + per-tenant topic/DLQ + Redis Streams mkstream BUSYGROUP
- **SEM STUB EM PROD** validate_for_production() 8 envs ?required + valid_ stub gated dev-only + TokenRefresh httpx real
- **PERSISTENCIA REAL** setex pipeline incr/expire + pool_pre_ping 3600 + backup pg_dump RC0 + BGSAVE ok (DDIA cap3)
- **CRIPTO** urlsafe_b64encode RS256+kid aud/iss/exp compare_digest sort_keys kid rotation v1->v2 dual-verify
- **LEAST PRIVILEGE** overwrite=False :ro CORS explicit enumerated pool_pre_ping 3600 allow_credentials False

## 5) Validacao

- `python scripts/verify_p6_data.py` 21/21 2x + `_validate_deep.py` 162/162 + `guard_anti_patterns.sh` 6/6 + pytest 40 + promtool 6/6 + compose healthy 7/7
- ADR-001 secao 4 rollout dual-verify -> publish v2 -> remove v1 sem downtime
