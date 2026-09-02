# Jefrey Threat Model

**Version**: 1.1  
**Created**: 2026-08-31  
**Last Updated**: 2026-09-02  
**Status**: FINAL - P4 Prod Hardening  

---

## 1. Overview

This threat model documents the security assumptions, assets, adversaries, and defense decisions for the Jefrey project. It formalizes the implicit security decisions that have been implemented throughout P1.3 and P2 development.

**Scope**: Jefrey AI agent system including:
- FastAPI backend (port 8000)
- MCP Gateway (port 8001)
- n8n Engine (port 5678)
- Postgres (port 5432) with pgvector
- Redis (port 6379)
- Ollama LLM (port 11434)
- Prometheus (port 9090) + Grafana (port 3000)

**Primary Audience**: Jefrey project maintainer, security reviewers, P3/P4 planning team

---

## 2. Adversary Model

### 2.1. Threat Actors

| Actor | Motivation | Capabilities | Likelihood |
|-------|-----------|-------------|------------|
| **Malicious User** | Extract data, disrupt service, gain unauthorized access | Can send arbitrary API requests, can craft tool calls, can manipulate conversation context | HIGH |
| **Compromised LLM Output** | Prompt injection, tool misuse, context manipulation | Can generate seemingly valid tool calls, can inject metadata, can manipulate conversation flow | HIGH |
| **External MCP Server** | Tool injection, data exfiltration, denial of service | Can expose arbitrary tools via MCP protocol, can return malicious data, can cause infinite loops | MEDIUM |
| **Internal Rogue Process** | Bypass RBAC, access unauthorized data, disrupt approvals | Can authenticate with valid user_id, can manipulate internal state, can bypass rate limits | LOW |
| **Network Attacker** | Intercept data, modify requests, replay attacks | Can sniff traffic (if no TLS), can modify packets in transit, can perform replay | MEDIUM (mitigated by TLS) |

### 2.2. Attack Vectors (Prioritized)

| # | Vector | Impact | Existing Mitigation | Gap |
|---|--------|--------|--------------------|-----|
| 1 | **Prompt Injection via Tool Calls** (CIPHER-011) | Data exfiltration, unintended actions | Content guard (15+ patterns), tool output sanitization | **PARTIAL** - guard active but not comprehensive |
| 2 | **Unauthorized Tool Access** (CIPHER-001, CIPHER-032) | Unauthorized actions, data exposure | RBAC (3 roles), ToolRegistry explicit registration, PolicyEngine decisions | **MINIMAL** - all tools registered with risk/role |
| 3 | **Bearer Token Theft** (CIPHER-019, CIPHER-031) | Full account compromise, lateral movement | hmac.compare_digest for timing-safe comparison, /approvals prefix isolation | **ACTIVE** - validation passing |
| 4 | **Redis Data Corruption** (SEC-005) | Data loss, injection attacks | requirepass in docker-compose, dual-write audit fallback | **ACTIVE** - configured |
| 4 | **Hardcoded Credentials** (CIPHER-004, H4) | Full system compromise | Removed "jefrey" default, Field(default="", alias="JEFREY_DATABASE__PASSWORD") | **RESOLVED** |
| 5 | **Route Conflict** (CIPHER-005, H5) | Request routing errors, bypass security | /approvals mount at /approvals prefix (not /) | **RESOLVED** |
| 6 | **Timing Attacks on Token Comparison** (CIPHER-003) | Bypass auth via timing side-channel | hmac.compare_digest() in auth_middleware.py | **RESOLVED** |
| 7 | **User ID Leakage** (CIPHER-001, H1-H2) | Cross-user data access, privacy violation | user_id in stream config, user_id propagation to ChromaDB metadata | **RESOLVED** (H1-H2 fixed) |
| 8 | **Session Fixation/Replay** | Unauthorized session takeover | Token introspection (planned CIPHER-031), /approvals/pending isolation | **PLANNED** |

---


### 2.3 Novos vetores P4 (IdP, HNSW, Streams, kid rotation)

| # | Vector | Impact | Mitigacao P4 | Gap |
|---|--------|--------|-------------|-----|
| 9 | **IdP token theft / jti replay** (CIPHER-031) | Reuso de refresh_token, replay de access_token | token_refresh.py httpx POST token_uri + client_id/secret, validacao aud/iss/exp/kid/alg, revogacao via Redis sadd+expire 86400 (jti TTL = exp-now), valid_ stub apenas dev | RESOLVED (P4-02) |
| 10 | **EventBus replay** (CIPHER-033) | Replay de evento assinado fora da janela | HMAC user_id.timestamp.canonical + janela 5m (timestamp Z), dual-verify kid v1/v2, legacy v0 DeprecationWarning + metric EVENTBUS_KID_LEGACY_TOTAL sem user_id label | RESOLVED (P4-03) |
| 11 | **HNSW poisoning / cross-user leak** | Vetor de outro user retornado, recall degradado | Filtro user_id em pg_memory add/search/get (Axiom #2), HNSW m=16 ef64 + ix_user_created, content_guard redact_pii antes de indexar | RESOLVED (P4-06/M1-M3) |
| 12 | **HMAC kid rotation quebra Stream** | Mensagens antigas invalidas apos rotacao | ADR-001: HMAC_KEYS_JSON dict kid->key, dual-verify, rollout v1->v2 sem incluir kid no HMAC input, TTL Stream maxlen 10000 | RESOLVED (ADR-001) |

## 3. Assets & Their Protection

| Asset | Confidentiality | Integrity | Availability | Protection Mechanism |
|-------|----------------|-----------|--------------|---------------------|
| **Postgres Data** (user memories, memories_json) | HIGH | HIGH | MEDIUM | pgvector HNSW indexes, pg_backups, user_id isolation via metadata |
| **Redis Working Memory** | MEDIUM | MEDIUM | HIGH | TTL-based expiration, requirepass, _write_fallback dual-write |
| **Ollama LLM Outputs** | LOW | MEDIUM | HIGH | Content guard (pattern matching), no persistent storage by default |
| **API Endpoints** | HIGH | HIGH | HIGH | OAuth2 introspection (planned), Bearer token validation, hmac.compare_digest |
| **Approval Workflow Data** | HIGH | HIGH | MEDIUM | Postgres approvals table, ownership check in decide(), expires_at timestamps |
| **Tool Registry Metadata** | MEDIUM | MEDIUM | HIGH | Explicit registration with risk/role, fail-closed blocking of unknown tools |
| **User Conversation Context** | HIGH | MEDIUM | HIGH | user_id propagation, ChromaDB metadata isolation, session timeout |
| **MCP Protocol Messages** | MEDIUM | MEDIUM | HIGH | HMAC signing (planned CIPHER-033), content sanitization (CIPHER-011), rate limiting (CIPHER-026) |

---

## 4. Security Decisions & Rationale

### 4.1. Design Principles

| Decision | Rationale | Alternative Considered | Why This Choice |
|----------|-----------|----------------------|-----------------|
| **Fail-closed tool blocking** | Unknown tools should never execute; only explicitly registered tools run | Fail-open (allow unknown tools for usability) | Security first; tool discovery can come later (P4/P5) with explicit opt-in |
| **Server-side role resolution** (CIPHER-001) | Roles must be determined server-side, never trusted from client | Client-declared roles (X-Jefrey-Role header) | Prevents role spoofing; RBAC engine is authority |
| **hmac.compare_digest for token comparison** (CIPHER-003) | Timing-safe comparison prevents side-channel attacks | Standard `==` comparison | Essential for Bearer token security; negligible performance cost |
| **/approvals prefix mount** (CIPHER-005, H5) | Approvals API must not conflict with router endpoints | Mount at `/` (root) | Avoided route conflicts; /approvals prefix is explicit and isolated |
| **Removed hardcoded "jefrey" password** (CIPHER-004, H4) | No secrets in source code | `password: str = "jefrey"` default | Follows Docker/12-factor; env vars with aliases maintain Pydantic v2 compatibility |
| **Dual-write audit log** (CIPHER-025, SEC-005) | Audit records in both Postgres and Redis | Single-store audit | Redundancy ensures audit survives container restarts or Redis clears |
| **user_id propagation throughout** (CIPHER-001, H1-H2) | Every tool call and graph node must know the user | No user_id tracking | Enables per-user isolation, audit tracing, RBAC enforcement; cost is minimal |

### 4.2. Explicitly AcceptED RisKS

| Risk | Acceptance Rationale | Monitoring |
|------|---------------------|------------|
| **Redis as cleartext within Docker network** | Docker network isolation + requirepass; assumed trusted internal network | Docker network encryption (future: P6+) |
| **Ollama running without auth** | Assumed local-only deployment; Ollama security model assumes trusted environment | Network segmentation (future) |
| **MemoryManager metadata_json field** | JSON storage (vs JSONB) was chosen earlier; migration path exists | Planned P4 migration to JSONB (@>/->> operators) |
| **Events.py weakref usage** | Weak references can cause unexpected garbage collection | Explicit cleanup in smoke test; documented behavior |

---

## 5. Security Controls Inventory

### 5.1. Technical Controls

| Control | CIPHER/SEC | Location | Status |
|---------|-----------|----------|--------|
| **Bearer token timing-safe comparison** | CIPHER-003 | auth_middleware.py | ✅ Implemented |
| **Explicit ToolRegistry registration** | CIPHER-001 | core/registry.py | ✅ All tools registered |
| **HARDCODED PASSWORD REMOVAL** | CIPHER-004 | core/config.py | ✅ Resolved |
| **/approvals prefix mount** | CIPHER-005 | api/main.py | ✅ Implemented |
| **Content guard pattern matching** | CIPHER-011 | core/content_guard.py | ✅ 15+ patterns |
| **Dual-write audit log** | CIPHER-025 | core/audit.py | ✅ Postgres + Redis |
| **user_id in stream config** | H1 | core/agent.py | ✅ Implemented |
| **user_id in ChromaDB metadata** | H2 | core/memory.py | ✅ Implemented |
| **hmac.compare_digest** | CIPHER-003 | api/auth_middleware.py | ✅ Implemented |
| **Rate limiting per user/tool** | CIPHER-026 | core/rate_limit.py | ✅ Implemented (P2) |
| **Input parameter sanitization** | CIPHER-028 | core/policy.py | ✅ Implemented (P2) |
| **Enhanced audit logging with user_id** | CIPHER-029 | core/policy.py | ✅ Implemented (P2) |
| **n8n tool registrations with risk/role** | CIPHER-027 context | core/registry.py | ✅ 5 tools registered (P2) |
| **OAuth2 introspection** | CIPHER-031 | oauth2/introspect.py | ✅ P4-02 (jwt.decode aud/iss, hash, sismember TTL) |
| **Skill risk assessment** | CIPHER-032 | skills/risk_assessment.py + version.py | ✅ P4 (packaging semver, HITL MAJOR) |
| **EventBus HMAC signing + Streams** | CIPHER-033 | eventbus/publisher.py + subscriber.py (XADD/XREADGROUP, DLQ, kid v1/v2) | ✅ P4-03 |

### 5.2. Process Controls

| Control | Frequency | Owner | Status |
|---------|-----------|-------|--------|
| **Code review security checklist** | Per PR | Team lead | ✅ Ongoing |
| **Dependency vulnerability scan** | Weekly | CI/CD (planned) | 📋 P4 |
| **Secrets rotation review** | Quarterly | DevOps | ✅ No hardcoded secrets |
| **Threat model update** | At each P milestone | Maintainer | ✅ This document |
| **Penetration testing** | Before P8 external | External firm | 📋 P8 |

---

## 6. Incident Response

### 6.1. Incident Categories

| Category | Trigger | Immediate Action | Owner | Escalation |
|----------|---------|-----------------|-------|------------|
| **Auth Bypass** | Successful token forgery or bypass | Disable affected endpoint, rotate keys, investigate logs | Team lead | Security lead |
| **Tool Injection** | Malicious tool output or prompt injection | Content guard triggered, audit log entry, rate limit enforcement | PolicyEngine team | Team lead |
| **Data Exfiltration** | Unusual data patterns in audit logs or Redis | Freeze affected data flow, assess scope, notify compliance | Team lead | Security lead |
| **Redis Compromise** | requirepass bypass or unauthorized write | Restart Redis with new password, investigate write source, rollback if needed | DevOps | Team lead |
| **Approval Workflow Bypass** | Unapproved tool execution | Disable approvals endpoint, review approval log, update if needed | PolicyEngine team | Team lead |

### 6.2. Detection Signatures

| Signature | Detection Method | Alert Channel |
|-----------|-----------------|---------------|
| `TOOLS_BLOCKED_total` spike | Prometheus alert > 2σ above baseline | Grafana/Alertmanager |
| `APPROVALS_DENIED_total` unusual pattern | Query anomalies in Postgres approvals table | Grafana dashboard |
| `RATE_LIMIT_DENY_total` per user/tool | Rate limiter metrics | Prometheus + Grafana |
| `CONTENT_GUARD_TOTAL` pattern matches | Content guard counter | Prometheus |
| `MCP_UNKNOWN_TOOL_total` | ToolRegistry blocked calls | Prometheus + manual review |

---

## 7. Compliance & Legal

| Requirement | Status | Notes |
|-------------|--------|-------|
| **GDPR user data deletion** | PARTIAL | user_id isolation enables deletion; no formal DPA |
| **SOC 2 Type II** | NOT STARTED | Required for P8 external deployment |
| **PCI DSS** | NOT APPLICABLE | No payment processing in scope |
| **OWASP Top 10 coverage** | PARTIAL | A1 (Broken Access Control), A3 (Injection), A5 (Security Misconfig) addressed; others planned |

---

## 8. Change Log

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2026-08-31 | 1.0 | Initial threat model creation | Project maintainer |
| 2026-09-02 | 1.1 | P4 FINAL: IdP/jti/HNSW/Streams/kid rotation (ADR-001), SLOs CI/CD | Maintainer |
| 2026-09-02 | 1.1 | P4 FINAL: IdP/jti/HNSW/Streams/kid rotation (ADR-001), SLOs CI/CD | Maintainer |
| | | | |

---

## 7. Related Documents

- `P2_VALIDATION_REPORT.md` - Validation results for P2
- `P3_PLAN.md` - P3 plan with CIPHER-031/032/033
- `verify_cipher_fixes.py` - 32/32 CIPHER/SEC check suite
- `src/jefrey/core/policy.py` - PolicyEngine implementation
- `src/jefrey/core/registry.py` - ToolRegistry with risk/role

---

**Security Contact**: Project maintainer (Pedro)  
**Model Review**: Required before each P milestone (P3, P4, P5)  
**Next Review**: P3 planning review or upon CIPHER-031/032/033 implementation