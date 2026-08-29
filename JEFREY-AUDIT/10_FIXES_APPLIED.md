# 10 — Correções Aplicadas (BUG-1 a BUG-6)

**Data:** 2026-08-28
**Escopo:** Corrigir todos os achados de `09_VALIDATION_FINDINGS.md`.
**Validação final:** `compileall` limpo · `verify_p1.py` ✅ · `smoke_test.py` **7/7 em console cp1252** (sem `PYTHONIOENCODING`) · `MemoryManager` usa Redis + Postgres em runtime.

---

## BUG-1 — `RedisWorkingMemory.get_messages()` / `get_recent()` → `KeyError`
**Arquivo:** `src/jefrey/core/redis_memory.py`
**Causa:** `_message_classes()` era definido mas nunca invocado → `_TYPE_TO_CLASS` vazio → `_deserialize` fazia `_TYPE_TO_CLASS["human"]` e quebrava.
**Correção:** `_deserialize` agora chama `_message_classes()` (populando o mapa role→classe preguiçosamente) e usa default seguro (`classes.get("human")`), lançando `ValueError` claro se o tipo for desconhecido.
**Validação:** `get_messages via Redis -> ['HumanMessage', 'AIMessage']` (sem `KeyError`).

## BUG-2 — `MemoryManager` não conectava ao Redis
**Arquivo:** `src/jefrey/core/memory.py`
**Causa:** `RedisWorkingMemory` era criado sem `redis_url` → fallback de dict local; container Redis ocioso.
**Correção:** `RedisWorkingMemory(..., redis_url=s.redis.dsn)` (usa `RedisSettings.dsn` do `.env`). Mantém fallback local se o Redis cair.
**Validação:** `short_term._redis is None=False`, `uses Redis?=True`.

## BUG-3 — Filtro por `metadata_json` quebrado
**Arquivos:** `src/jefrey/core/models.py`, `src/jefrey/core/pg_memory.py`, `src/jefrey/core/schema.py`
**Causa:** coluna era `JSON` (não `JSONB`); `_build_filter` comparava `metadata_json -> key` com `=`/`IN` → `operator does not exist: json = character varying`.
**Correção:**
- `models.py`: `metadata_json` passa a ser `JSONB` (em `_MemoryMixin` e em `Approval.arguments_json`).
- `schema.py`: `init_db()` agora converte `metadata_json json -> jsonb` (idempotente via `DO $$ ... ALTER ... USING metadata_json::jsonb`) em DBs existentes.
- `pg_memory.py`: nova `_metadata_clause` — `$eq`/`$ne` usam containment `@>` (passando o **dict Python** ao `cast(..., JSONB)` para o driver serializar em objeto jsonb correto; `json.dumps` fazia o psycopg re-serializar a string e quebrar o `@>`), `$in` usa `->> IN (...)`, e comparadores numéricos (`$gt` etc.) fazem `cast(... AS numeric)`.
**Validação:** `verify_p1.py` ganha testes de `metadata_json` (`eq` + `$in`); probe confirma `eq`/`$in`/`$gte` OK.

## BUG-4 — `.env` de produção incompleto (Postgres/Redis inativos)
**Arquivo:** `.env`
**Causa:** só tinha `JEFREY_LLM__PROVIDER=ollama`; faltavam `PROVIDER`, `REDIS__URL`, `DATABASE__URL`.
**Correção:** acrescentados (preservando o provider `ollama` que funciona):
```
JEFREY_MEMORY__LONG_TERM__PROVIDER=postgres
JEFREY_DATABASE__URL=postgresql+psycopg://jefrey:jefrey@localhost:5432/jefrey
JEFREY_DATABASE__POOL_SIZE=10 / MAX_OVERFLOW=20
JEFREY_REDIS__URL=redis://localhost:6379/0
JEFREY_MEMORY__LONG_TERM__EMBEDDING_DIM=768
JEFREY_MEMORY__SHORT_TERM__MAX_MESSAGES=20 / MAX_TOKENS=8000
```
**Consistência de dimensão:** `nomic-embed-text` (Ollama) gera **768** dims; `.env` e `verify_p1` (`EMBED_DIM = get_settings().memory.long_term.embedding_dim`) passam a usar 768, e o schema foi recriado (`drop_all`+`create_all`) para `vector(768)`. Sem isso, inserts dariam `expected 768 dimensions, not 1536`.

## BUG-5 — `events.py`: anotação enganosa / `weakref` não usado
**Arquivo:** `src/jefrey/core/events.py`
**Correção:** removido `import weakref`; anotações de `_handlers`/`_wildcard_handlers` passam a `list[EventHandler]` (o fix do P0 já armazena referências fortes corretamente).

## BUG-6 — Smoke test morria em console `cp1252`
**Arquivo:** `scripts/smoke_test.py`
**Correção:** no topo, `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` e mesmo para `stderr` (envolvido em `try/except`), evitando `UnicodeEncodeError` ao renderizar emojis do `rich`.
**Validação:** `python scripts/smoke_test.py` (console cp1252, sem `PYTHONIOENCODING`) → **7/7 PASS**.

---

## Conclusão
Todos os 6 achados de `09` estão corrigidos e revalidados. Fase 0 e Fase 1 seguem verdes; o agente agora usa **Postgres+pgvector (longo prazo) + Redis (working memory)** de fato, e os filtros por `metadata_json` funcionam. Próximo marco natural: **P2** (OpenAI Agents SDK & Responses API + checkpointer Postgres no lugar do `MemorySaver` do LangGraph).
