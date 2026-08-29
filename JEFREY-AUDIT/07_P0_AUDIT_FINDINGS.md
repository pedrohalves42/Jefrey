# Phase P0 — Physical Audit Findings & Baseline Report

**Date:** 2026-08-28
**Scope:** Static + dynamic audit of the existing `src/jefrey` (and `src/jarvis`) codebase, smoke-test validation, and import resolution.

---

## 1. Executive Summary

The existing **Jefrey** codebase is a functional personal-assistant skeleton built on **LangGraph + LangChain**, with **ChromaDB** as the long-term vector store and **Ollama/OpenAI/Anthropic** LLM bindings. The skill system, event bus, and memory manager are well-structured.

After fixing a series of import/wiring bugs, the baseline smoke test now passes **7 / 7** checks. The foundation is solid enough to begin the migration toward the production target architecture (PostgreSQL + pgvector + Redis, OpenAI Agents SDK, MCP, n8n, security layers).

> Note: The current core uses **LangGraph** (state-machine graph), not yet the **OpenAI Agents SDK / Responses API** targeted in Phase P2. This is expected — P0 only baselines the existing system.

---

## 2. Baseline Test Results (`scripts/smoke_test.py`)

| Test | Status | Notes |
|------|--------|-------|
| Configuration | ✅ PASS | Settings load correctly from `config/settings.yaml` |
| Memory | ✅ PASS | Short + long-term memory operational (ChromaDB) |
| Skills Loading | ✅ PASS | 3 skills, 15 tools loaded |
| Basic Agent | ✅ PASS | `JefreyAgent` health-check returns `healthy` |
| Skill Notes (CRUD) | ✅ PASS | Save / search / list / get / update / delete |
| Skill Web Search | ✅ PASS* | Skipped (no `TAVILY_API_KEY`) — graceful degradation |
| Event Bus | ✅ PASS | Handlers + wildcards fire correctly |

*\*PASS reported because the test intentionally skips when the API key is absent.*

---

## 3. Bugs Found & Fixed (P0)

| # | Severity | File | Issue | Fix |
|---|----------|------|-------|-----|
| 1 | High | `scripts/smoke_test.py` | `sys.path` only added `src/`, so `from src.jefrey...` imports failed (`No module named 'src'`). | Added repo root to `sys.path` before `src/`. |
| 2 | High | `src/jefrey/skills/__init__.py` | `@tool` decorator returned a `StructuredTool` directly from a **classmethod/bound method**, dropping `self` → `missing 1 required positional argument: 'self'` at invocation. | Converted decorator to return a `ToolDescriptor` that resolves the bound method via `__get__` and builds the `StructuredTool` lazily per-instance. |
| 3 | Medium | `src/jefrey/skills/notes.py` | `save_note` / `update_note` used `**metadata`, which collided with Pydantic `args_schema` (raised `Field required: metadata`). | Replaced with an explicit `metadata: dict[str, Any] | None = None` parameter. |
| 4 | Medium | `src/jefrey/core/events.py` | `EventBus` stored handlers as `weakref.ref`; local test lambdas were garbage-collected before emission, so wildcard handlers silently never fired. | Replaced weak-ref storage with strong references + simplified `_emit_to_handlers` (no dead-ref cleanup). |
| 5 | Medium | `src/jefrey/core/memory.py` | ChromaDB rejects non-primitive metadata (lists/dicts) → `Expected metadata value to be a str, int, float or bool, got []`. | Added `_to_chroma_metadata` / `_from_chroma_metadata` JSON-(de)serializers applied at `add` / `update` / `get` / `search` / `list_recent`. Forward-compatible with the future pgvector backend. |

---

## 4. Architecture Observations

- **Agent core (`src/jefrey/core/agent.py`):** LangGraph `StateGraph` with nodes `load_context → reasoning → (execute_tools) → format_response → save_memory`. Uses `MemorySaver` checkpointer (in-memory; **not** durable — must move to Postgres in P1). LLM bound via `langchain` providers.
- **Memory (`src/jefrey/core/memory.py`):** `ShortTermMemory` (in-RAM deque buffer) + `LongTermMemory` (ChromaDB persistent client + embedding cache). `MemoryManager` facade exposes combined context.
- **Skills (`src/jefrey/skills/`):** `SkillBase` ABC + `SkillRegistry` + auto-registration decorator `@skill`. Notes, web_search, calendar, email, automation present. Calendar/email skills log init failures (google-api-python-client not installed) but degrade gracefully.
- **Events (`src/jefrey/core/events.py`):** Decoupled async `EventBus` with domain event constants (`SystemEvents`).
- **Config (`src/jefrey/core/config.py`):** Pydantic settings loaded from YAML. Defaults to `ollama` provider + `chromadb` memory.

---

## 5. Risk Register (carried into P1–P4)

| Risk | Impact | Target Phase |
|------|--------|--------------|
| In-memory `MemorySaver` checkpointer → no durable conversation state | High | P1 (Postgres) |
| ChromaDB/SQLite → no ACID, no RLS, no unified operational+semantic store | High | P1 (pgvector) |
| No RBAC / guardrails / HITL | Critical | P4 |
| OpenAI Agents SDK / Responses API not yet adopted | Medium | P2 |
| No MCP gateway / n8n bridge | Medium | P3 |
| No observability (OTel/Prometheus) | Medium | P6 |
| Optional integrations (Google Calendar/Gmail) uninstalled | Low | P1/P5 |

---

## 6. Recommendation / Next Step

Proceed to **Phase P1**: stand up PostgreSQL (pgvector) + Redis via Docker Compose and introduce a SQLAlchemy-backed `LongTermMemory` / operational store behind the existing `MemoryManager` interface, keeping the ChromaDB implementation as a fallback adapter. This unblocks durable checkpoints, RLS, and the 6-layer memory model.

Baseline is **green**. The migration can begin without destabilizing current behavior.
