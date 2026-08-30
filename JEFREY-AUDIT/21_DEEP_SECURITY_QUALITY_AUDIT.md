# Jefrey — Deep Security & Quality Audit
**Date**: 2026-08-30  
**Scope**: Full codebase security + quality review for production commercial deployment  

---

## 1. SECRET LEAKAGE IN GIT HISTORY

### Finding: ✅ CLEAN — No secrets found in git history
- `git log --all --diff-filter=D -- "*.env" "*.key" "*.pem" "*.p12"` returned **no results**
- `git log --all --name-only --oneline -- "*.env"` returned **no results**
- `git log --all --diff-filter=A` for secret files returned **no results**

**Assessment**: No `.env`, `.key`, `.pem`, or `.p12` files were ever committed and deleted. Git history is clean.

---

## 2. HARDCODED SECRETS IN SOURCE CODE

### Finding: ⚠️ MEDIUM — Hardcoded database credentials

| File | Line | Issue | Severity |
|------|------|-------|----------|
| `src/jefrey/core/config.py` | 165 | `password: str = "jefrey"` | **MEDIUM** |
| `docker-compose.yml` | 14 | `POSTGRES_PASSWORD: jefrey` | **MEDIUM** |
| `docker-compose.yml` | 31 | Redis has **NO password configured** | **HIGH** |

**Details**:
- **Database password hardcoded as default**: `DatabaseSettings.password = "jefrey"`. This is a Pydantic Settings default, which means it CAN be overridden via env vars (`JEFREY_DATABASE__PASSWORD`). However, if the env var isn't set, the hardcoded value is used. For production, the docker-compose.yml passes `POSTGRES_PASSWORD: jefrey` matching this default.
- **Redis has no authentication**: `redis:7.2-alpine` runs with no `--requirepass` flag. Combined with the port mapping `"6379:6379"`, **any process on the network can connect to Redis**.
- **No API keys hardcoded**: All API keys (`api_key`, `secret_key`, etc.) are loaded from env vars via Pydantic Settings. No `tvly-`, `sk-`, `ghp_`, or other API key patterns found in source.

**Recommendation**:
- Use strong, unique passwords for both Postgres and Redis in production
- Add `requirepass` to Redis command args
- Remove port mappings for internal services (Postgres, Redis) in production

---

## 3. ERROR MESSAGES LEAKING INFORMATION

### Finding: 🔴 HIGH — `str(e)` leaks internal details to API responses

**30 instances of `str(e)` in error responses across the codebase:**

#### API Layer (user-facing):

| File | Line | Leaked Data |
|------|------|-------------|
| `src/jefrey/api/chat.py` | 197, 248 | `raise HTTPException(status_code=500, detail=f"Erro na execução: {e}")` — full exception string |
| `src/jefrey/api/memory.py` | 43 | `raise HTTPException(status_code=500, detail=str(e))` — raw exception |
| `src/jefrey/api/memory.py` | 64 | `"error": str(e)` in health endpoint |

**Impact**: Python exceptions can contain:
- Internal file paths (`/home/user/jarvis/src/...`)
- Database connection strings (with passwords)
- Stack trace fragments
- Library version info
- Internal hostnames and IPs

**Critical Example** (`chat.py:197`):
```python
raise HTTPException(status_code=500, detail=f"Erro na execução: {e}")
```
If the Postgres connection fails, `str(e)` could return something like:
```
could not connect to server: Connection refused Is the server running on host "localhost" (127.0.0.1) and accepting TCP/IP connections on port 5432?
```

**Recommendation**: Replace all `str(e)` in HTTP responses with generic messages. Log the full error server-side only.

---

## 4. INPUT VALIDATION

### Finding: 🔴 HIGH — Critical missing validations

#### 4a. chat.py — Missing input length limits
```python
class ChatRequest(BaseModel):
    message: str       # ← NO max_length constraint
    thread_id: str = "default"  # ← NO max_length, NO pattern validation
```

**DoS vectors**:
- **Unbounded message length**: A client can send a multi-GB string. The `sanitize_tool_output()` call will regex match against it, consuming massive CPU. Then the LLM call will process it.
- **Arbitrary thread_id**: No format validation. Attacker can create unlimited `_RUNNING_TASKS` entries by using unique thread_ids, causing memory exhaustion (each entry holds a reference to an asyncio.Task).
- **No rate limiting**: Zero rate limiting on any endpoint. A simple loop of POST /chat requests can exhaust the event loop.

#### 4b. memory.py — Missing search query validation
```python
q: str = Query(..., description="Termo ou frase para busca semântica na memória"),
limit: Optional[int] = Query(5, ...),  # ← NO upper bound on limit
```
- **No max limit**: Client can set `limit=999999999` to trigger massive ChromaDB/Postgres queries
- **No min length on `q`**: Empty-ish strings (spaces only) are caught, but single-char queries are fine — this is OK

#### 4c. approvals.py — Reasonably validated
- UUID validation on approval_id ✅
- Decision validation (approved/rejected only) ✅  
- But: `decided_by` field has no length limit or sanitization ⚠️

#### 4d. chat.py thread_id DoS
```python
task_key = f"{user_id}:{thread_id}"
if task_key in _RUNNING_TASKS and not _RUNNING_TASKS[task_key].done():
    return {"status": "running", ...}
```
A malicious client can create **unlimited entries** in `_RUNNING_TASKS` by sending rapid requests with unique `thread_id` values. Each entry holds an `asyncio.Task` reference. No eviction policy beyond the 60s cleanup (which only removes done tasks).

**Recommendations**:
- Add `max_length=10000` to `ChatRequest.message`
- Add `max_length=128, pattern=r"^[a-zA-Z0-9_-]+$"` to `thread_id`
- Add `Query(limit, le=100)` cap on memory search limit
- Add rate limiting middleware (slowapi or similar)
- Add max size for `_RUNNING_TASKS` dict

---

## 5. CONCURRENCY ISSUES

### Finding: ⚠️ MEDIUM — Race conditions in `_RUNNING_TASKS`

#### 5a. Check-then-act race in chat.py
```python
if task_key in _RUNNING_TASKS and not _RUNNING_TASKS[task_key].done():
    return {"status": "running", ...}

# ... (gap between check and assignment)

task = asyncio.create_task(_run_agent_task())
_RUNNING_TASKS[task_key] = task
```

Since FastAPI runs on a single-threaded asyncio event loop, this specific pattern is actually **safe** — there's no true parallel execution of Python code between the `if` and the assignment. **However**, this relies on the assumption that no `await` occurs between the check and assignment. Currently true, but fragile if someone adds code later.

#### 5b. `_RUNNING_TASKS` is a plain dict — no memory limits
```python
_RUNNING_TASKS: Dict[str, asyncio.Task] = {}
```
- No maximum size — unbounded memory growth possible
- The `_cleanup_stale_tasks()` only runs every 60 seconds and only removes completed tasks
- Between cleanups, completed tasks still hold references to their results in the Task object

#### 5c. `RedisWorkingMemory` session isolation
```python
def session(self, session_id: str) -> "RedisWorkingMemory":
    return RedisWorkingMemory(
        session_id=session_id,
        ...
    )
```
The `MemoryManager.__init__` creates `RedisWorkingMemory(session_id="default")` — **all conversations share the same session**. The `session_id` parameter exists but is never called from the agent loop. This means:
- All users share the same short-term memory buffer
- There's NO per-thread isolation in short-term memory (only in long-term via user_id)

**Impact**: User A's conversation context bleeds into User B's context. This is a **data leakage / privacy issue**.

#### 5d. `_EmbeddingCache` thread-safety
The `_EmbeddingCache` uses `threading.Lock()` which is correct, but in an asyncio context, this lock **blocks the event loop** when contended. For CPU-bound work, this should use `asyncio.Lock()` or run in a thread pool.

**Recommendations**:
- Add `max_tasks` limit to `_RUNNING_TASKS` (e.g., 100)
- Pass thread_id as session_id to RedisWorkingMemory for proper isolation
- Use asyncio-compatible locks

---

## 6. SMOKE TEST "Memória" FAILURE — ROOT CAUSE

### Finding: 🔴 CRITICAL — Smoke test fails due to external service dependencies

The `test_memory()` function in `scripts/smoke_test.py`:

```python
async def test_memory():
    from src.jefrey.core.memory import get_memory_manager
    mem = get_memory_manager()
    
    # 1. Tests short-term memory
    mem.short_term.add_user("Olá")
    mem.short_term.add_assistant("Oi!")
    
    # 2. Tests long-term memory
    note_id = mem.long_term.add("Teste de memória", metadata={"test": True})
    results = mem.long_term.search("memória", top_k=1)
    assert len(results) >= 1    # ← THIS FAILS
```

**Root Cause Analysis**:

1. `get_memory_manager()` → `MemoryManager()` → imports `RedisWorkingMemory` and creates either `PostgresLongTermMemory` or `LongTermMemory` (ChromaDB)

2. **If Postgres provider (production config)**:
   - `PostgresLongTermMemory.search()` requires a running PostgreSQL with pgvector extension
   - The `add()` call uses `user_id="system"` (default) 
   - The `search()` call also uses `user_id="system"` (default)
   - **If Postgres is not running**: `get_db()` raises a connection error → smoke test fails with connection refused
   - **If Postgres IS running**: The `add()` succeeds, but `search()` does a **cosine distance query with embedding**. The embedding requires Ollama to be running (for `nomic-embed-text` model). If Ollama is down, the search fails.

3. **If ChromaDB provider (default fallback)**:
   - `LongTermMemory.__init__` tries to create `chromadb.PersistentClient` and `OllamaEmbeddings`
   - `LongTermMemory.search()` calls `self._embeddings.embed_query(query)` — requires Ollama
   - The `add()` call also embeds via Ollama — if Ollama is down, it fails

**The most likely failure scenario**: Ollama is not running (or not accessible at `http://localhost:11434`), causing the embedding calls to fail. The error message would be about connection refused to Ollama.

**Secondary failure**: Even if Ollama is running, the `search()` could return 0 results if:
- The embedding model produces different embeddings for "memória" vs "Teste de memória"
- The similarity threshold (0.7) filters out the result
- ChromaDB is not properly persisting to disk

**Recommendations**:
- The smoke test should mock external dependencies (Ollama, Postgres, Redis) or use in-memory backends
- Add `try/except` with clear error messages indicating which service is unavailable
- Consider a `--mode=unit` flag that uses mock/in-memory backends
- The test's assertion `len(results) >= 1` is fragile — ChromaDB cosine similarity on a single document may not meet the 0.7 threshold

---

## 7. MISSING .GITIGNORE ENTRIES

### Finding: ✅ GOOD — Most entries present, but minor gaps

**.gitignore contents**:
```
.env, .env.local, .env.*.local  ✅
__pycache__/                     ✅
*.py[cod], *.pyo                 ✅
logs/, *.log                     ✅
data/                            ✅
*.sqlite3                        ✅
pgdata/, redis_data/, n8n_data/  ✅
```

**Missing/Weak entries**:
| Entry | Status | Risk |
|-------|--------|------|
| `*.pyc` (case-insensitive) | ✅ Covered by `*.py[cod]` | None |
| `data/` | ✅ Present | None |
| `logs/` | ✅ Present | None |
| `.env` | ✅ Present | None |
| `config/tokens/` | ❌ **MISSING** | Token files for Google Calendar/Gmail could be committed |
| `config/credentials/` | ⚠️ Only n8n version covered | `config/credentials/*.json` (Google OAuth secrets) not explicitly ignored |
| `*.rar` (jarvis.rar in root) | ❌ **MISSING** | Binary archive is tracked |
| `Dockerfile.*.local` | ❌ Missing | Local Docker overrides could leak |
| `*.env.*` (not just `.local`) | ⚠️ Only `.env.*.local` covered | `.env.production` etc. would be committed |

**Critical**: `config/tokens/google_calendar_token.json` and `config/tokens/gmail_token.json` paths exist in config defaults. If these token files are created during OAuth flow, they could be committed because `config/tokens/` is not gitignored. The `jarvis.rar` file (0 bytes) is already tracked in the repo.

---

## 8. DOCKER SECURITY

### Finding: 🔴 HIGH — Multiple security issues

#### 8a. Running as root
Both Dockerfiles run as **root** (no `USER` directive):
```dockerfile
# Dockerfile.api
FROM python:3.12-slim
WORKDIR /app
# ← No USER instruction — runs as root!
```
**Impact**: If an attacker achieves code execution in the container, they have root access.

#### 8b. Hardcoded database password in docker-compose.yml
```yaml
environment:
  POSTGRES_USER: jefrey
  POSTGRES_PASSWORD: jefrey  # ← Hardcoded weak password
```

#### 8c. No Redis authentication
```yaml
redis:
  image: redis:7.2-alpine
  command: ["redis-server", "--appendonly", "yes"]
  ports:
    - "6379:6379"  # ← Exposed to host with NO password
```
**Impact**: Any process on the host can read/write Redis data (short-term memory, session data).

#### 8d. Internal service ports exposed to host
```yaml
ports:
  - "5432:5432"  # Postgres exposed to host
  - "6379:6379"  # Redis exposed to host
  - "8000:8000"  # API exposed
  - "8001:8001"  # MCP exposed
  - "5678:5678"  # n8n exposed
```
Postgres and Redis should NOT be exposed to the host in production. They should only be accessible within the Docker network.

#### 8e. Source code mounted as volume
```yaml
volumes:
  - .:/app  # ← Full source code including .env mounted into container
```
If the container is compromised, the attacker can read `.env` with all secrets and modify source code.

#### 8f. CORS allows all origins
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ← Allows ANY origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
**Impact**: Any website can make authenticated requests to the Jefrey API if the browser has the Bearer token (e.g., via XSS or token theft).

#### 8g. No read-only filesystem
Containers don't use `read_only: true` or `tmpfs` mounts. Combined with running as root, an attacker can write anywhere.

#### 8h. No resource limits
No `mem_limit`, `cpus`, or `deploy.resources` configured. A single container can consume all host resources.

#### 8i. n8n `N8N_SECURE_COOKIE: "false"`
```yaml
N8N_SECURE_COOKIE: "false"
```
Session cookies are not secure — vulnerable to interception over HTTP.

#### 8j. No network isolation
All services communicate on the default bridge network. There's no separation between internal (Postgres/Redis) and external-facing (API/n8n) services.

---

## 9. ADDITIONAL FINDINGS

### 9a. No Content-Length / request body size limit
FastAPI has no `max_body_size` configuration. An attacker can send arbitrarily large request bodies to exhaust memory.

### 9b. SQL Injection: ✅ Protected
All database queries use SQLAlchemy ORM with parameterized queries. The `_build_filter()` function in `pg_memory.py` properly uses SQLAlchemy column operations. No raw SQL with string interpolation found.

### 9c. Prompt Injection: Partially mitigated
- `content_guard.py` blocks common injection patterns ✅
- But the blocklist is minimal (7 patterns). Advanced injections can bypass it.
- User input goes through `sanitize_tool_output()` but this same function is designed for tool **output**, not user **input** — the name is misleading and the patterns are output-focused.

### 9d. `_RUNNING_TASKS` memory leak on server restart
Tasks in `_RUNNING_TASKS` are lost on server restart (in-memory dict). But `ApprovalManager.get_pending()` queries the database, which survives restarts. So approvals created by crashed tasks remain in "pending" state forever — they'll eventually expire via `expire_due()`, but there's no active cleanup mechanism.

### 9e. `settings = get_settings()` at module level in config.py
```python
# Para compatibilidade
settings = get_settings()
```
This is called at import time, which means ALL env vars are read when any module imports `config.py`. This is fine but couples import order to environment readiness.

### 9f. Debug mode enabled by default
```python
class AppSettings(BaseSettings):
    debug: bool = True  # ← Default is True!
```
If `.env` doesn't set `JEFREY_DEBUG=false`, debug mode is on in production. This enables `reload=cfg.debug` in uvicorn, which should never be on in production.

### 9g. Tool executor doesn't validate user_id propagation
`ToolExecutor.__init__` accepts `user_id` but defaults to `"system"`. The `_execute_tools` method in `agent.py` creates `ToolExecutor` without passing `user_id`:
```python
executor = ToolExecutor(
    tool_resolver=tool_map.get,
    actor_role=resolve_role(),
    autonomous=False,
    thread_id=state.thread_id,
)
```
Missing: `user_id` is not passed. It defaults to `"system"`, which means all tool executions are attributed to "system" regardless of which user initiated them. This breaks the multi-tenant isolation.

---

## SEVERITY SUMMARY

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | Git history clean | ✅ OK | Pass |
| 2 | Hardcoded DB password / no Redis auth | ⚠️ MEDIUM | Needs fix |
| 3 | `str(e)` leaks internals in API responses | 🔴 HIGH | Needs fix |
| 4 | No input length/rate limiting (DoS) | 🔴 HIGH | Needs fix |
| 5 | Short-term memory not isolated per user | 🔴 HIGH | Needs fix |
| 6 | Smoke test fails (external deps) | ⚠️ MEDIUM | Needs fix |
| 7 | Missing gitignore entries (tokens, credentials) | ⚠️ MEDIUM | Needs fix |
| 8 | Docker: root user, exposed ports, CORS *, debug default | 🔴 CRITICAL | Needs fix |
| 9a | No request body size limit | ⚠️ MEDIUM | Needs fix |
| 9b | SQL injection safe | ✅ OK | Pass |
| 9c | Prompt injection partial mitigation | ⚠️ LOW | Accept |
| 9d | Orphaned approvals on restart | ⚠️ LOW | Accept |
| 9e | Module-level settings load | ✅ OK | Pass |
| 9f | Debug=True default | ⚠️ MEDIUM | Needs fix |
| 9g | user_id not propagated to ToolExecutor | 🔴 HIGH | Needs fix |

---

## PRIORITY FIXES (Production Blockers)

### P0 — Must fix before production:
1. **Add non-root USER to Dockerfiles** and add `read_only: true`
2. **Set `debug: bool = False`** as default
3. **Replace `str(e)` in all HTTP responses** with generic error messages
4. **Add input validation** (max_length on message, thread_id pattern, rate limiting)
5. **Add Redis authentication** and remove port mappings for internal services
6. **Restrict CORS** to specific origins
7. **Propagate user_id to ToolExecutor** for proper multi-tenant isolation
8. **Pass thread_id as session_id** to RedisWorkingMemory for short-term memory isolation
9. **Add `.env.production`, `config/tokens/`, `config/credentials/`** to .gitignore

### P1 — Should fix soon:
1. Add request body size limits
2. Add resource limits to Docker containers
3. Use Docker secrets or vault for database passwords
4. Add network isolation (internal vs external)
5. Fix smoke test to use mocked backends
