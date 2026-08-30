# Deep Code Review — Jefrey Project (P0–P6)

**Reviewer**: Subagent 20260830_11  
**Date**: 2026-08-30  
**Scope**: 24 files across Infrastructure, Memory, Agent, MCP, Security, API, Observability

---

## Executive Summary

The codebase is **well-structured** with consistent patterns, thorough security annotations, and good defensive coding. The P4 security layer (RBAC → PolicyEngine → HITL → Audit) is architecturally sound. However, there are several issues ranging from HIGH (security/logic) to LOW (style/docs).

**Total findings: 42**  
- 🔴 HIGH: 8  
- 🟠 MEDIUM: 18  
- 🟢 LOW: 16  

---

## P0/P1 — Infrastructure

### `src/jefrey/core/db.py`

| # | Severity | Issue |
|---|----------|-------|
| 1 | 🟠 MEDIUM | **Module-level singleton with no thread safety** — `_engine` and `_SessionLocal` are set via `global` without locks. In a multi-threaded FastAPI/uvicorn server, two concurrent requests could both enter `if _engine is None` and create duplicate engines. Should use `threading.Lock()` or `functools.lru_cache`. |
| 2 | 🟢 LOW | **No docstring on `get_db()` context manager** — the type hint `Iterator[Session]` is correct but no Args/Returns docstring. |
| 3 | 🟢 LOW | **No type hint on `_engine`** — should be `_engine: Engine | None = None` for clarity. |

### `src/jefrey/core/models.py`

| # | Severity | Issue |
|---|----------|-------|
| 4 | 🟠 MEDIUM | **`server_default="'system'"` is a SQL string literal** — `Column(String(128), server_default="'system'")` inserts the literal string `'system'` (with quotes). The default Python-side should match. The quotes are part of the SQL default expression. If the intent is just `system`, it should be `server_default="system"` (without surrounding quotes in the SQL). |
| 5 | 🟢 LOW | **`MEMORY_TABLES` dict is populated at module import time** — if `get_settings()` fails (e.g., missing .env), the entire models module fails to import. This couples config to model definition. Consider lazy resolution. |
| 6 | ✅ GOOD | `user_id` column present on all memory tables and Approval/AuditLog with index — user_id isolation pattern is consistent. |
| 7 | ✅ GOOD | `AuditLog` model has CIPHER-010 annotation. |

### `src/jefrey/core/schema.py`

| # | Severity | Issue |
|---|----------|-------|
| 8 | 🟠 MEDIUM | **SQL injection in JSONB migration block** — The f-string interpolation `f"WHERE table_name = '{name}_memory'"` uses `name` from `MEMORY_TABLES` keys which are hardcoded ("episodic", "semantic", etc.), so it's not directly exploitable. However, if `MEMORY_TABLES` ever gets populated from external input, this becomes SQL injection. Should use parameterized queries or at minimum add a comment that keys are trusted. |
| 9 | 🟢 LOW | **No type hint on `init_db()` return** — already returns `None` explicitly, but could add `-> None` annotation (it's present). |

### `src/jefrey/core/config.py`

| # | Severity | Issue |
|---|----------|-------|
| 10 | 🔴 HIGH | **Hardcoded default password `password: str = "jefrey"` in `DatabaseSettings`** — This is a real security risk. Even though it's a default, it ships in the codebase and will be used in development unless overridden. If the dev database is exposed (port 5432 on 0.0.0.0), this is exploitable. Recommend removing the default or using a random default with a warning. |
| 11 | 🔴 HIGH | **`debug: bool = False` is good, but `validate_for_production()` only checks `secret_key`** — It does NOT check if `debug=True` in production, nor does it validate that `DatabaseSettings.password` is not the default `"jefrey"`. The validation is incomplete for production safety. |
| 12 | 🟠 MEDIUM | **`settings = get_settings()` at module level** — This creates a global singleton at import time. If `.env` is missing or malformed, the entire config module fails to load. The comment says "lazy" but the bottom line `settings = get_settings()` defeats that. |
| 13 | 🟢 LOW | **`api_key: str = ""` in `EmbeddingsSettings`** — empty string default could silently fall through to `None`-like behavior. Should be `Optional[str] = None` for clarity. |
| 14 | 🟢 LOW | **No docstrings on most Settings subclasses** — `LLMSettings`, `DatabaseSettings`, etc. lack class-level docstrings explaining what they configure. |

### `scripts/db_init.py`

| # | Severity | Issue |
|---|----------|-------|
| 15 | ✅ GOOD | Clean, minimal bootstrap script. Delegates to `schema.init_db()`. |

---

## P1 — Memory

### `src/jefrey/core/pg_memory.py`

| # | Severity | Issue |
|---|----------|-------|
| 16 | 🟠 MEDIUM | **`_build_filter` trusts `filter_metadata` keys for JSONB `->>` operations** — While known column keys are whitelisted (`_COLUMN_KEYS`), the `else` branch for unknown keys does `col.op("->>")(key)` which accesses arbitrary JSONB keys. An attacker could craft metadata keys to enumerate JSONB structure. This is low-risk since it's internal, but the code comment about "injecao/robustez" should be verified. |
| 17 | 🟠 MEDIUM | **`update()` mutates `metadata` dict in-place via `metadata.pop()`** — The caller's dict is mutated, which is a side-effect bug. Should copy: `metadata = dict(metadata)`. |
| 18 | 🟢 LOW | **`import time as _time` inside methods** — Repeated in `add()`, `search()`. Should be a module-level import. |
| 19 | ✅ GOOD | **User isolation is thorough** — `get()`, `update()`, `delete()` all check `rec.user_id != user_id`. `search()` and `list_recent()` pass `user_id` through `_build_filter`. |
| 20 | ✅ GOOD | Metrics (`MEMORY_OPS`, `MEMORY_LATENCY`) are instrumented on both success and exception paths. |

### `src/jefrey/core/memory.py`

| # | Severity | Issue |
|---|----------|-------|
| 21 | 🔴 HIGH | **`LongTermMemory` (ChromaDB) has NO user_id isolation** — `add()`, `search()`, `get()`, `update()`, `delete()`, `list_recent()` do not accept or filter by `user_id`. The `PostgresLongTermMemory` is properly isolated, but the ChromaDB fallback is completely open. If a user selects the chromadb provider (default!), all users share memory with zero isolation. |
| 22 | 🟠 MEDIUM | **`MemoryManager.get_context()` calls `self.long_term.search(current_query)` without user_id** — Even with the Postgres backend, this call passes no `user_id` (defaults to `"system"`). Any user query would search only `user_id="system"` memories, not their own. The `get_context()` method needs a `user_id` parameter. |
| 23 | 🟠 MEDIUM | **`MemoryManager.save_important_memory()` has no `user_id` parameter** — Always uses the default `"system"`. Memories saved by users are attributed to `system`, breaking multi-tenant isolation. |
| 24 | 🟢 LOW | **`CachedEmbeddings.embed_documents()` has a logic bug** — `uncached_texts.index(idx)` uses `idx` (which is the original index in the full list) to look up in `uncached_texts` (which only has uncached items). This would throw `ValueError` if there are cached items. The correct index should be tracked separately. |
| 25 | 🟢 LOW | **`from chromadb.config import Settings as ChromaSettings`** at module level — ChromaDB is a heavy dependency that may not be installed. This will cause ImportError on import if ChromaDB is not installed, even if the user only wants the Postgres backend. |

### `src/jefrey/core/redis_memory.py`

| # | Severity | Issue |
|---|----------|-------|
| 26 | 🟠 MEDIUM | **No TTL on Redis keys** — `_save()` uses `self._redis.set(self._key(), ...)` without an expiry. Old session data persists forever in Redis. Should set a TTL (e.g., 24h) for cleanup. |
| 27 | 🟢 LOW | **`__len__` calls `self._load()` without lock** — In a concurrent scenario, `_load()` reads from Redis which is fine, but the load-trim-save cycle in `add()` could race. The `_lock` in `add()` protects this, but `__len__` doesn't. Minor since Redis GET is atomic. |
| 28 | ✅ GOOD | Redis fallback to local memory is clean and logged. |

---

## P2 — Agent

### `src/jefrey/core/agent.py`

| # | Severity | Issue |
|---|----------|-------|
| 29 | 🔴 HIGH | **`stream()` does not propagate `user_id`** — The `initial_state` in `stream()` does not set `user_id=user_id` (unlike `run()`). This means the agent's `AgentState.user_id` defaults to `"system"` when streaming, breaking multi-tenant isolation in the streaming path. |
| 30 | 🟠 MEDIUM | **`_execute_tools` catches `Exception` and returns `str(e)` in results** — Line `results.append({"tool_call_id": tool_id, "name": tool_name, "error": str(e)})` puts the raw error into the result dict, which gets serialized as a `ToolMessage` back to the LLM. This could leak internal details (DB connection strings, stack traces) to the LLM context. Should use a sanitized error message. |
| 31 | 🟠 MEDIUM | **`_load_context` inserts memory as SystemMessage at index 0** — `state.messages.insert(0, SystemMessage(...))` mutates the list in-place and inserts at position 0. If `load_context` is called multiple times (e.g., retries), memories stack up. Also, this pushes the original system prompt (added in `_reasoning`) after the memory, which may confuse the LLM. |
| 32 | 🟢 LOW | **`_load_skill_prompts()` reads files from `config/prompts/skills/` at every reasoning step** — This is I/O on the hot path. Should be cached at init time. |
| 33 | 🟢 LOW | **`_save_memory` creates a new `session()` but doesn't persist** — It calls `self.memory.short_term.session(state.thread_id)` to get a thread-scoped session but adds messages there. These messages are saved to Redis (via the session), but the main `self.memory.short_term` is not updated, creating a potential inconsistency. |
| 34 | ✅ GOOD | `run()` correctly propagates `user_id` to both `AgentState` and `ToolExecutor`. |

---

## P3 — MCP

### `src/jefrey/mcp/client.py`

| # | Severity | Issue |
|---|----------|-------|
| 35 | 🟢 LOW | **`_ROOT = Path(__file__).resolve().parents[3]` + `sys.path.insert`** — This is a workaround for import path issues. Should be resolved via proper package installation (pyproject.toml). |
| 36 | ✅ GOOD | `MCPClientError` is a clean exception class that doesn't leak stack traces (`__str__` returns only `self.message`). |
| 37 | ✅ GOOD | CIPHER-011: `sanitize_tool_output()` is called on MCP tool output before returning to caller. |
| 38 | ✅ GOOD | `register_explicit()` forces manual tool registration (no auto-discovery), reducing attack surface. |

### `src/jefrey/mcp/server.py`

| # | Severity | Issue |
|---|----------|-------|
| 39 | 🟠 MEDIUM | **`exec(src, ns)` in `_make_wrapper()` dynamically generates Python code** — While the `src` is built from controlled schema fields, this is still code generation via `exec()`. If a tool's `args_schema` has unusual annotations, the generated code could fail in unexpected ways. Consider using `inspect.signature` manipulation instead. |
| 40 | 🟠 MEDIUM | **Error message in `_run_guarded` leaks exception type** — `f"[ERRO NA FERRAMENTA] {tool.name}: {e}"` returns the raw exception string to the MCP caller. The `_stringify` function also does `str(result)` which could include internals. |
| 41 | ✅ GOOD | CIPHER-001: Role is resolved server-side, never from caller payload. |
| 42 | ✅ GOOD | CIPHER-018: Tool timeout is applied via `asyncio.wait_for()`. |

---

## P4 — Security

### `src/jefrey/core/rbac.py`

| # | Severity | Issue |
|---|----------|-------|
| 43 | ✅ GOOD | Clean, minimal RBAC with 3 roles (guest/user/admin) and rank-based comparison. |
| 44 | ✅ GOOD | `resolve_role()` delegates to config, never trusts caller (CIPHER-022). |
| 45 | 🟢 LOW | **`@require_role` decorator stores metadata but doesn't enforce anything** — It's purely documentary. The actual enforcement is in `register_default_tools()`. Could confuse developers into thinking the decorator is protective. |

### `src/jefrey/core/policy.py`

| # | Severity | Issue |
|---|----------|-------|
| 46 | 🟠 MEDIUM | **`_POLICY` singleton is not thread-safe** — `get_policy_engine()` uses a global `_POLICY` variable with no lock. Two concurrent calls could both see `None` and create duplicate instances. Low impact (idempotent) but technically a race condition. |
| 47 | ✅ GOOD | AXIOM #5 (fail-safe for unregistered tools) is properly implemented: `UNKNOWN` → DENY. |
| 48 | ✅ GOOD | Admin bypass (AXIOM #4) is correctly gated and audited. |

### `src/jefrey/core/hitl.py`

| # | Severity | Issue |
|---|----------|-------|
| 49 | 🟠 MEDIUM | **`decide()` reads `_tool_name` from the row but doesn't close session before accessing `r.tool_name`** — Actually, it does: `_tool_name = r.tool_name` is captured before `get_db()` context exits. This is correct. ✅ |
| 50 | 🟢 LOW | **`wait_for_decision()` polls with `asyncio.sleep()`** — In a high-approval scenario, this creates many concurrent polling coroutines. Consider a pub/sub pattern (e.g., Redis pub/sub or asyncio.Event) for production. |
| 51 | ✅ GOOD | Ownership check in `decide()` prevents cross-user approval. |
| 52 | ✅ GOOD | `expire_due()` is called before reads to ensure stale approvals are cleaned. |

### `src/jefrey/core/executor.py`

| # | Severity | Issue |
|---|----------|-------|
| 53 | 🟠 MEDIUM | **`_invoke()` returns error strings for unresolvable tools** — `return f"[ERRO] ferramenta '{tool_name}' não resolvida"` — this string goes back to the LLM as a tool result, which could be interpreted as instruction. Should be wrapped in a clear block marker. |
| 54 | ✅ GOOD | CIPHER-023: Synchronous tool calls run in `asyncio.to_thread()` to avoid blocking the event loop. |
| 55 | ✅ GOOD | Full audit trail on every path (allow, deny_rbac, deny, hitl, approved, rejected, expired). |

### `src/jefrey/core/audit.py`

| # | Severity | Issue |
|---|----------|-------|
| 56 | ✅ GOOD | CIPHER-025: Fallback to local file when Postgres is down — dual-write ensures forensic trail. |
| 57 | 🟢 LOW | **Fallback file has no rotation or size limit** — `data/audit_fallback.jsonl` grows unbounded. Should add log rotation or max size check. |

### `src/jefrey/core/content_guard.py`

| # | Severity | Issue |
|---|----------|-------|
| 58 | 🟠 MEDIUM | **`re.IGNORECASE` on all patterns means case-insensitive matching** — Pattern `r"<s>"` would match `<S>` as well. The token patterns (`<s>`, `</s>`, `[INST]`, etc.) are case-sensitive in actual LLM formats, so case-insensitive matching creates false positives (e.g., legitimate content containing `<S>` in HTML). |
| 59 | 🟠 MEDIUM | **Pattern `r"(Human|Assistant|System):"` matches inside any word** — No word boundary `\b` before/after. The string "The Human: is coming" would be blocked. This is overly aggressive for user input content guard. |
| 60 | 🟢 LOW | **Duplicate pattern** — `r"</s>"` appears twice in `_INJECTION_PATTERNS`. |
| 61 | 🟢 LOW | **No rate limiting on content_guard** — If an attacker sends many blocked messages, they flood the log with warnings. |

### `src/jefrey/core/registry.py`

| # | Severity | Issue |
|---|----------|-------|
| 62 | ✅ GOOD | Fail-safe: unregistered tools get `UNKNOWN` risk and are blocked by PolicyEngine. |
| 63 | 🟢 LOW | **`_registered` flag is module-level global** — If `register_default_tools()` is called from multiple threads, the flag could be read as `True` before all registrations complete. Low impact since `register()` is idempotent. |

---

## P5 — API

### `src/jefrey/api/main.py`

| # | Severity | Issue |
|---|----------|-------|
| 64 | 🔴 HIGH | **`app.mount("/", approvals_app)` mounts Starlette on root** — This means the approvals sub-app catches ALL routes not matched by FastAPI routers first. Since it's mounted at `/`, routes like `/chat` or `/memory` could potentially be intercepted by the Starlette app's `_AuthMiddleware` (which requires Bearer token) before reaching the FastAPI routers. The mount order matters — FastAPI routes are checked first, but the Starlette middleware stack runs on ALL requests. This could cause authentication bypass or double-auth issues depending on middleware ordering. |
| 65 | 🟠 MEDIUM | **CORS `allow_headers=["*"]`** — While `allow_origins` is restricted, allowing all headers means `Authorization`, `X-User-Id`, and any custom headers pass through. In production, this should be restricted to `["Authorization", "X-User-Id", "Content-Type"]`. |
| 66 | 🟢 LOW | **No `/metrics` in `_PUBLIC_PATHS`** — The metrics endpoint is registered via a FastAPI router (which goes through the auth middleware). Prometheus scraping requires either adding `/metrics` to `_PUBLIC_PATHS` or passing the Bearer token in the scrape config. |

### `src/jefrey/api/chat.py`

| # | Severity | Issue |
|---|----------|-------|
| 67 | 🔴 HIGH | **`_RUNNING_TASKS` dict is in-memory** — In a multi-worker deployment (uvicorn with `--workers > 1`), each worker has its own `_RUNNING_TASKS` dict. A user could bypass the concurrency check (`if task_key in _RUNNING_TASKS`) by hitting different workers. Also, after a restart, all tasks are lost but the dict is empty, so stale approvals in the DB won't be cleaned. Should use Redis for distributed task tracking. |
| 68 | 🟠 MEDIUM | **`chat()` creates `JefreyAgent()` on every request** — This is expensive (loads skills, creates LLM, builds graph, compiles with checkpointer). Should be a singleton or injected. |
| 69 | 🟠 MEDIUM | **`chat()` exception handler returns generic message but logs full error** — The `HTTPException(status_code=500, detail="Erro interno na execução. Tente novamente.")` is correct for user-facing, but the `logger.error` includes `exc_info=True` which logs the full traceback to stdout. In production, this could be noisy. Consider structured logging with redaction. |
| 70 | 🟢 LOW | **`ChatRequest.message` has `max_length=10000`** — Reasonable, but there's no corresponding truncation in the agent. A 10k-char message will be sent to the LLM which may hit token limits. |
| 71 | ✅ GOOD | Thread-scoped concurrency prevention via `task_key = f"{user_id}:{thread_id}"`. |
| 72 | ✅ GOOD | Content guard applied to user input before agent execution. |

### `src/jefrey/api/memory.py`

| # | Severity | Issue |
|---|----------|-------|
| 73 | 🟠 MEDIUM | **`search_memory()` calls `mm.long_term.search(q, limit=limit, user_id=user_id)`** — The `LongTermMemory` (ChromaDB) backend doesn't accept `user_id` parameter (see finding #21). If the chromadb backend is used, the `user_id` kwarg will be ignored or cause a TypeError. |
| 74 | 🟢 LOW | **`memory_health()` is public (no auth)** — Returns aggregate memory stats. This is acceptable for monitoring but could leak operational details. |

### `src/jefrey/api/approvals.py`

| # | Severity | Issue |
|---|----------|-------|
| 75 | ✅ GOOD | CIPHER-019: Bearer token auth on all routes. |
| 76 | ✅ GOOD | CIPHER-020: `arguments_json` omitted from `/approvals/pending` response. |
| 77 | ✅ GOOD | CIPHER-024: UUID validation before DB access. |
| 78 | 🟢 LOW | **`_DEFAULT_USER = "anonymous"`** — Requests without `X-User-Id` default to "anonymous". This could allow an unauthenticated caller (if the Bearer check is bypassed) to see/decide approvals for "anonymous" user. Since CIPHER-019 protects the auth, this is low risk. |

### `src/jefrey/api/auth_middleware.py`

| # | Severity | Issue |
|---|----------|-------|
| 79 | 🟠 MEDIUM | **Timing attack on Bearer token comparison** — `auth != f"Bearer {secret}"` uses Python's `!=` which short-circuits on first differing character. Should use `hmac.compare_digest()` for constant-time comparison to prevent timing side-channel attacks on the secret key. |
| 80 | 🟢 LOW | **`_PUBLIC_PATHS` doesn't include `/metrics`** — Prometheus scraping may fail if metrics endpoint requires auth. |

---

## P6 — Observability

### `src/jefrey/core/metrics.py`

| # | Severity | Issue |
|---|----------|-------|
| 81 | ✅ GOOD | Low-cardinality labels (no user_id, no content). |
| 82 | ✅ GOOD | Buckets are well-chosen for each metric type. |
| 83 | 🟢 LOW | **No `LLM_TOKENS` or `LLM_COST` instrumentation in agent.py** — These counters are defined but never incremented anywhere in the reviewed code. Dead metrics. |

### `src/jefrey/core/instrumentation.py`

| # | Severity | Issue |
|---|----------|-------|
| 84 | 🟢 LOW | **`_is_async` imports `asyncio` on every call** — Should be module-level. |
| 85 | 🟢 LOW | **Decorators are defined but `@timed`/`@counted` are not used anywhere** in the reviewed codebase. The agent uses `@traceable` from Langsmith instead. These are dead code unless planned for future use. |
| 86 | ✅ GOOD | Both sync and async functions are supported. |

### `src/jefrey/api/metrics_endpoint.py`

| # | Severity | Issue |
|---|----------|-------|
| 87 | 🟢 LOW | **No auth on `/metrics` endpoint** — This is standard for Prometheus, but if the metrics contain sensitive label values (they don't currently), this could be an issue. |
| 88 | ✅ GOOD | Clean, minimal implementation using `generate_latest()`. |

---

## Cross-Cutting Findings

### Circular Import Analysis

| Path | Status |
|------|--------|
| `config` → `db` → `config` | ✅ OK (db imports config, not vice versa) |
| `models` → `config` | ✅ OK (models imports config for EMBED_DIM) |
| `memory` → `pg_memory` → `memory` | ⚠️ **Potential cycle**: `pg_memory.py` imports `get_embeddings` from `memory.py` lazily inside `__init__`. `memory.py` imports `pg_memory` lazily inside `MemoryManager.__init__()`. This works because both are lazy, but is fragile. |
| `policy` → `registry` → `policy` | ⚠️ **Potential cycle**: `registry.py` imports `RiskLevel` from `policy.py` lazily inside `register_default_tools()`. `policy.py` imports `TOOL_REGISTRY` from `registry.py` at module level. This works because `register_default_tools()` is called lazily, but is fragile. |
| `core/__init__.py` → agent → policy → registry | ✅ OK (all lazy imports) |

### Hardcoded Secrets/Passwords

| File | Issue | Severity |
|------|-------|----------|
| `config.py` | `password: str = "jefrey"` in DatabaseSettings | 🔴 HIGH |
| `config.py` | `secret_key: str = ""` in APISettings | ✅ OK (empty = deny-all) |

### Error Handling Quality

| File | Leaks stack traces? | Notes |
|------|---------------------|-------|
| `chat.py` | ✅ No | Returns generic 500 message |
| `approvals.py` | ✅ No | Returns structured error JSON |
| `pg_memory.py` | ⚠️ Partial | `health_check()` returns `str(e)` |
| `agent.py` | ⚠️ Partial | `_execute_tools` puts `str(e)` in tool results sent to LLM |
| `mcp/client.py` | ✅ No | `MCPClientError.__str__` returns only message |
| `mcp/server.py` | ⚠️ Partial | `_run_guarded` returns `f"...{e}"` |

### User ID Isolation Audit

| Component | user_id Propagated? | Notes |
|-----------|---------------------|-------|
| `run()` | ✅ Yes | `user_id` → `AgentState` → `ToolExecutor` |
| `stream()` | ❌ **No** | `user_id` NOT set in `initial_state` |
| `get_context()` | ❌ **No** | No `user_id` param → defaults to `"system"` |
| `save_important_memory()` | ❌ **No** | No `user_id` param |
| `pg_memory.*()` | ✅ Yes | All methods filter by `user_id` |
| `chroma_memory.*()` | ❌ **No** | No `user_id` support at all |
| `approval.*()` | ✅ Yes | `create()`, `decide()`, `get_pending()` filter by `user_id` |
| `chat.py` endpoints | ✅ Yes | All extract `user_id` from `request.state` |

---

## Priority Fix Recommendations

### 🔴 Fix Immediately (HIGH)

1. **`agent.py` `stream()` missing user_id** — Add `user_id=user_id` to `AgentState` in `stream()` (same pattern as `run()`).
2. **`memory.py` ChromaDB backend has no user isolation** — Either add `user_id` to ChromaDB metadata filtering, or remove ChromaDB as an option and default to Postgres.
3. **`config.py` hardcoded password** — Change `password: str = "jefrey"` to `password: str = ""` or `password: Optional[str] = None` with validation in `validate_for_production()`.
4. **`main.py` mount order** — Move `app.mount("/", approvals_app)` to `app.mount("/approvals", approvals_app)` to prevent route conflicts with FastAPI routers.
5. **`auth_middleware.py` timing attack** — Replace `auth != f"Bearer {secret}"` with `hmac.compare_digest(auth, f"Bearer {secret}")`.
6. **`chat.py` in-memory task tracking** — Document that single-worker mode is required, or implement Redis-backed task tracking.
7. **`config.py` incomplete `validate_for_production()`** — Add checks for `debug=True`, default database password, and empty `allowed_roles`.
8. **`memory.py` `get_context()` / `save_important_memory()` missing user_id** — Thread `user_id` through `MemoryManager` methods.

### 🟠 Fix Soon (MEDIUM)

- `db.py` thread safety for singleton creation
- `chat.py` agent instantiation per request (make singleton)
- `auth_middleware.py` restricted CORS headers
- `content_guard.py` false positive reduction (add word boundaries)
- `redis_memory.py` add TTL to Redis keys
- `pg_memory.py` update() mutates caller's dict
- `schema.py` f-string SQL (add safety comment)
- `agent.py` error string leaking to LLM context
- `mcp/server.py` exec() code generation
- `policy.py` singleton thread safety

### 🟢 Nice to Have (LOW)

- Docstrings on all Settings classes
- Module-level imports (not in-method)
- Dead code cleanup (`LLM_TOKENS`, `LLM_COST`, `@timed`, `@counted`)
- Audit fallback file rotation
- `CachedEmbeddings.embed_documents()` index bug fix
- Duplicate `</s>` pattern in content_guard
- `/metrics` in `_PUBLIC_PATHS`

---

## Security Annotations Audit

All CIPHER references found and verified:

| Annotation | File | Status |
|-----------|------|--------|
| CIPHER-001 | `config.py`, `rbac.py`, `mcp/server.py` | ✅ Role never from caller |
| CIPHER-010 | `models.py` (AuditLog), `audit.py` | ✅ Forensic audit trail |
| CIPHER-011 | `mcp/client.py` | ✅ External output sanitized |
| CIPHER-012 | `mcp/server.py` | ✅ approval_id truncated in response |
| CIPHER-018 | `config.py`, `mcp/server.py` | ✅ Tool timeout enforced |
| CIPHER-019 | `config.py`, `approvals.py`, `auth_middleware.py` | ✅ Bearer auth on HITL |
| CIPHER-020 | `approvals.py` | ✅ arguments_json omitted |
| CIPHER-021 | `policy.py` | ✅ RBAC always runs |
| CIPHER-022 | `rbac.py`, `agent.py` | ✅ Server-side role resolution |
| CIPHER-023 | `executor.py` | ✅ Sync tools in to_thread |
| CIPHER-024 | `approvals.py` | ✅ UUID validation |
| CIPHER-025 | `config.py`, `audit.py` | ✅ Fallback dual-write |

---

*End of Deep Code Review*
