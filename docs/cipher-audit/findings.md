# CIPHER AUDIT - JEFREY ASSISTANT
# Date: 2026-09-07
# Scope: P0-P5

=== ARCHITECTURE SUMMARY ===
1. FastAPI :8000 REST API (chat, memory, approvals, STT, TTS)
2. Auth middleware: Bearer token (dev-key OR OAuth2 introspection)
3. POST /chat -> JefreyAgent -> Ollama LLM via httpx -> response
4. Governance pipeline: RBAC -> PolicyEngine -> RateLimit -> HITL -> Execute
5. Memory: PostgresLongTermMemory (pgvector HNSW) + RedisShortTermMemory
6. HITL: ApprovalManager polls approvals table, wait_for_decision blocks
7. MCP: streamable-http and stdio transports
8. EventBus: HMAC-SHA256 signed events with kid rotation
9. STT: faster-whisper, TTS: ElevenLabs/pyttsx3
10. Docker: 7 services, read_only filesystem, non-root

=== CRITICAL FINDINGS ===

CRIT-01: agent.py TRIPLE AgentState class definition (FATAL)
  File: src/jefrey/core/agent.py lines 23-60
  Three AgentState class definitions from failed edit attempts
  Last definition __setattr__ self[name]=value conflicts with __init__
  VERIFIED: AgentState(user_id='test').user_id returns '' not 'test'
  Impact: Chat ALWAYS returns Internal Server Error
  Severity: CRITICA

CRIT-02: agent.py run() BYPASSES all governance (FATAL)
  File: src/jefrey/core/agent.py run() method
  Direct httpx POST to Ollama, never calls _invoke() or any tool
  RBAC, PolicyEngine, HITL, content_guard, AuditLogger = DEAD CODE
  Severity: CRITICA

CRIT-03: resume_chat/get_chat_status return raw dict not string
  File: src/jefrey/api/chat.py lines 175-180, 262-270
  task.result() returns dict, resume returns nested dict as response
  Severity: ALTA

CRIT-04: stt.py calls PolicyEngine.decide() which DOES NOT EXIST
  File: src/jefrey/api/stt.py lines 35-45
  PolicyEngine has evaluate() not decide() -> AttributeError -> 500
  Severity: ALTA

CRIT-05: tts.py same PolicyEngine API mismatch
  File: src/jefrey/api/tts.py lines 35-45
  Severity: ALTA

CRIT-06: memory.py health_check DEAD CODE after return
  File: src/jefrey/core/memory.py line 175
  health_check() defined after return in get_memory_manager()
  Severity: ALTA

=== HIGH FINDINGS ===

HIGH-01: memory_api.py wrong method names
  File: src/jefrey/api/memory.py lines 45-65
  mm.long_term.search() should be mm.search()
  mm.short_term.get_messages() does not exist
  Severity: ALTA

HIGH-02: pg_memory search() uses importance sort NOT vector similarity
  File: src/jefrey/core/pg_memory.py line 85
  ORDER BY importance DESC instead of cosine distance
  Severity: ALTA

HIGH-03: pg_memory _embed() method NEVER DEFINED
  File: src/jefrey/core/pg_memory.py line 55
  add() calls self._embed(content) -> AttributeError always
  Severity: ALTA

HIGH-04: Rate limiter fails in Docker (no password in URL)
  File: src/jefrey/core/rate_limit.py
  redis.dsn builds URL without password, Redis requires auth
  ALL tools denied by rate limiter -> RuntimeError -> deny
  Severity: ALTA

HIGH-05: Skills do NOT propagate user_id
  Files: skills/automation.py, calendar.py, drive.py, email.py
  Only notes.py has user_id -> cross-tenant data leak
  Severity: ALTA

HIGH-06: Approvals no admin check for HIGH/CRITICAL
  File: src/jefrey/api/approvals.py decide()
  CIPHER-111 only logs warning, does not BLOCK auto-approval
  Severity: ALTA

=== MEDIUM FINDINGS ===

MED-01: _RUNNING_TASKS lost on Docker restart
  File: src/jefrey/api/chat.py line 35
  In-memory dict, no persistence
  Severity: MEDIA

MED-02: approvals _UserContextMiddleware trusts X-User-Id header
  File: src/jefrey/api/approvals.py line 55
  Any client can impersonate users via header
  Severity: ALTA (IDOR vector)

MED-03: signing.py dev key fallback
  File: src/jefrey/eventbus/signing.py
  Weak key if JEFREY_ENV misconfigured as dev in prod
  Severity: MEDIA

MED-04: content_guard does NOT sanitize LLM output
  File: src/jefrey/core/agent.py
  LLM response used directly without injection check
  Severity: MEDIA

MED-05: SSRF blocking incomplete
  File: src/jefrey/api/connections.py
  Misses: 0.0.0.0, DNS rebinding, some IPv6
  Severity: MEDIA

MED-06: HITL approve race condition (no SELECT FOR UPDATE)
  File: src/jefrey/core/hitl.py decide()
  Two concurrent approves both see pending
  Severity: MEDIA

MED-07: CLI memory search missing user_id
  File: src/jefrey/cli/main.py
  Sends Bearer but no X-User-Id -> anonymous -> 0 results
  Severity: ALTA

=== LOW/INFORMATIVE FINDINGS ===

LOW-01: Auth middleware dead code after exception block
  File: src/jefrey/api/auth_middleware.py lines 100-105
  Severity: INFORMATIVA

LOW-02: LLM base_url strips /v1
  File: src/jefrey/core/config.py line 25
  Severity: BAIXA

LOW-03: Checkpoint not namespaced by user_id
  File: src/jefrey/core/checkpointer.py
  Thread_id collision possible across users
  Severity: MEDIA

=== REGRESSION CHECK ===

CIPHER-001 (auth bypass via user_role): OPEN - approvals X-User-Id trust
CIPHER-002 (WindowsSelectorEventLoop): MITIGATED - Linux Docker
CIPHER-019 (HITL REST auth): FIXED - _AuthMiddleware present
CIPHER-025 (HMAC key fail-closed): FIXED - RuntimeError when missing
CIPHER-021 (dev-token prod): FIXED - is_prod check present
CIPHER-026 (rate limit fail-closed): PARTIAL - Redis URL issue

=== PONTOS FORTES ===

PF-01: Timing-safe token comparison (auth_middleware.py:80)
PF-02: Audit dual-write fallback (audit.py:_write_fallback)
PF-03: Dev-token blocked in prod (auth.py:is_prod)
PF-04: Rate limiting fail-closed (rate_limit.py)
PF-05: Content guard 30+ injection patterns (content_guard.py)
PF-06: CORS fail-closed (main.py)
PF-07: Memory isolation via user_id filter (memory.py)
PF-08: DB session with proper rollback/close (db.py)
PF-09: Approval expiry mechanism (hitl.py:expire_due)
PF-10: No raw SQL anywhere (SQLAlchemy ORM only)