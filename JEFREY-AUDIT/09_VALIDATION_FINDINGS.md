# 09 — Validação Fase 0 + Fase 1 (Auditoria de Sintaxe & Lógica)

**Data:** 2026-08-28
**Escopo:** Revalidar Fase 0 e Fase 1, produzir resumo e caçar erros de sintaxe/lógica em todo o código entregue.
**Ambiente:** Python 3.14.7, Windows 11 (cmd), Docker Compose v5.4.0, containers `jefrey-postgres` (ankane/pgvector:latest) e `jefrey-redis` (redis:7.2-alpine) em `healthy`.

---

## 1. Resultado da Validação (Status de Aceitação)

| Validação | Comando | Resultado |
|---|---|---|
| **P0 — Smoke Test** | `python scripts/smoke_test.py` | ✅ **7/7 PASS** (com `PYTHONIOENCODING=utf-8`; ver BUG-6) |
| **P1 — E2E Postgres+pgvector** | `python scripts/verify_p1.py` | ✅ PASS — schema, insert, busca (sim=0.289), filtro de tag, update/delete, `episodic=1` |
| **P1 — Redis Working Memory** | (em verify_p1) | ✅ PASS — 2 mensagens, `wm.session()` preserva, `len=2`, tokens=7 |
| **P1 — Docker Compose** | `docker compose ps` | ✅ `postgres` + `redis` `Up` / `healthy` |
| **P1 — Init Schema** | `python scripts/db_init.py` | ✅ extension `vector` + tabelas + índices HNSW criados |
| **Sintaxe — `src/`** | `python -m compileall src` | ✅ sem erros de sintaxe |
| **Sintaxe — `scripts/`** | `python -m compileall scripts` | ✅ sem erros de sintaxe |
| **Sintaxe — docker-compose.yml** | `docker compose config` (implícito) | ✅ parseado (containers sobem) |

> Sem **nenhum** erro de sintaxe em `.py` ou no compose. Os "problemas" são de **lógica/runtime** e de **configuração** (abaixo).

---

## 2. Resumo do que foi Entregue

### Fase 0 — Auditoria física + estabilização (7/7)
- `JEFREY-AUDIT/00..08` (checklists, arquitetura, roadmap P0–P8, plano n8n/MCP, achados P0/P1).
- `skills/__init__.py`: decorator `@tool` → `ToolDescriptor` (resolve método bound via `__get__`, eliminando o erro de `self` ausente).
- `core/events.py`: `EventBus` com referências fortes (corrige wildcards GC'd).
- `skills/notes.py`: `save_note`/`update_note` com param `metadata` explícito + `tags` no meta.
- `core/memory.py`: `LongTermMemory` (ChromaDB) com `_to_chroma_metadata`/`_from_chroma_metadata` (serializa list/dict).
- `scripts/smoke_test.py`: 7 testes (config, memória, skills, agente, notes, web search, event bus).

### Fase 1 — Backend durável (Postgres + pgvector + Redis) — VERIFICADO E2E
- `docker-compose.yml`: `postgres` (ankane/pgvector) + `redis` (7.2-alpine, appendonly).
- `core/db.py`: engine singleton (pool_pre_ping), `sessionmaker`, `get_db()` ctx-manager (commit/rollback/close).
- `core/models.py`: `Base` + 5 tabelas de memória (`_MemoryMixin`) + `Approval` (HITL P4).
- `core/schema.py`: `init_db()` → extension `vector`, `create_all`, índices HNSW `vector_cosine_ops`.
- `core/pg_memory.py`: `PostgresLongTermMemory` (interface ChromaDB-compat: add/search/get/update/delete/list_recent/count) + `_build_filter`.
- `core/redis_memory.py`: `RedisWorkingMemory` por sessão (Redis primário, fallback local).
- `core/config.py`: `DatabaseSettings`/`RedisSettings` (+ `dsn`) e `embedding_dim`.
- `core/memory.py` (`MemoryManager`): seleção de backend por `provider` (ChromaDB preservado, zero breaking change).
- `requirements.txt`, `.env.example`, `scripts/db_init.py`, `scripts/verify_p1.py`.

---

## 3. Erros de Lógica / Runtime Encontrados (confirmados por execução)

### 🔴 BUG-1 — `RedisWorkingMemory.get_messages()` / `get_recent()` quebram com `KeyError`
- **Onde:** `src/jefrey/core/redis_memory.py` — `_deserialize()` + `_message_classes()` (nunca chamado).
- **Causa:** `_TYPE_TO_CLASS` começa `{}` e só seria populado por `_message_classes()`, que **não é invocado em lugar nenhum**. `_deserialize` faz `_TYPE_TO_CLASS.get(d["role"], _TYPE_TO_CLASS["human"])` → o default `_TYPE_TO_CLASS["human"]` levanta `KeyError` porque o dict está vazio.
- **Impacto:** Qualquer recuperação de mensagens objetos falha. `agent._load_context` → `get_context` → `short_term.get_messages()` e `agent._save_memory` → `short_term.get_messages()` **crasham em runtime** (tanto no fallback local quanto no Redis). `to_dict()` funciona (não desserializa), por isso `verify_p1` (que só confere `len()`/`token_count`) mascarou o bug.
- **Evidência:** `get_messages FAILED -> KeyError('human')`.
- **Correção sugerida:** popular `_TYPE_TO_CLASS` na importação (chamar `_message_classes()` no final do módulo) **ou** fazer `_deserialize` chamar `_message_classes()` e usar default seguro (`_TYPE_TO_CLASS.get(d["role"], HumanMessage)`).

### 🔴 BUG-2 — `MemoryManager` nunca conecta ao Redis (usa fallback em memória)
- **Onde:** `src/jefrey/core/memory.py` → `MemoryManager.__init__`.
- **Causa:** `RedisWorkingMemory(session_id="default", max_messages=..., max_tokens=...)` é criado **sem `redis_url` nem `redis_client`**. Dentro de `RedisWorkingMemory`, a conexão só é tentada `if self._redis is None and redis_url is not None` → com `redis_url=None` cai no fallback de dict local. O container Redis (rodando) **nunca é usado** pelo manager padrão.
- **Impacto:** A working memory do agente é in-process e volátil; o Redis da Fase 1 fica ocioso na prática. `verify_p1` só exercita Redis porque passa `redis_url="redis://localhost:6379/0"` explícito.
- **Evidência:** `MANAGER short_term._redis is None=True`, `uses Redis?=False`.
- **Correção sugerida:** `RedisWorkingMemory(..., redis_url=get_settings().redis.dsn)` (ou passar um cliente).

### 🟠 BUG-3 — Filtro por `metadata_json` está quebrado (caminho não testado)
- **Onde:** `src/jefrey/core/pg_memory.py` → `_build_filter()` (ramo `else`: `col = table.metadata_json[key]`).
- **Causa:** `metadata_json` é `Column(JSON, ...)` (não `JSONB`). `table.metadata_json[key]` gera `metadata_json -> key` que retorna `json`; comparar com `=`/`IN` contra um varchar falha: `operator does not exist: json = character varying`.
- **Impacto:** `search`/`list_recent` com filtros em chaves de `metadata_json` (ex.: `{"project": "x"}`) lançam `ProgrammingError`. `verify_p1` só testa filtro de `tags` (ARRAY, via `&&`), então esse ramo ficou sem cobertura.
- **Evidência:** `UndefinedFunction: operator does not exist: json = character varying` em ambos `$eq` e `$in`.
- **Correção sugerida:** mudar `metadata_json` para `JSONB`; em `_build_filter`, para chaves de metadata usar `@>` (containment, para `$eq`) e `->>` (texto, para `$in`/`$ne`/range com cast `::numeric`). Adicionar teste de filtro metadata em `verify_p1`.

### 🟡 BUG-4 — `.env` de produção incompleto (Postgres/Redis inativos)
- **Onde:** `.env` (arquivo ativo) vs `.env.example`.
- **Causa:** o `.env` real contém apenas `JEFREY_LLM__PROVIDER=ollama`. Faltam `JEFREY_MEMORY__LONG_TERM__PROVIDER=postgres`, `JEFREY_REDIS__URL`, `JEFREY_DATABASE__URL`, `EMBEDDING_DIM`.
- **Impacto:** mesmo com containers no ar, o app cai em ChromaDB + dict local (confirmado: `MANAGER long_term type=LongTermMemory`). `.env.example` está correto; o `.env` precisa espelhá-lo.
- **Correção sugerida:** copiar `.env.example` → `.env` e preencher chaves; garantir `PROVIDER=postgres` + `REDIS__URL`.

### 🟡 BUG-5 — `events.py`: anotação enganosa / `weakref` não usado em lógica
- **Onde:** `src/jefrey/core/events.py` (`__init__` anota `list[weakref.ref]`; importa `weakref`).
- **Causa:** o fix do P0 armazena **referências fortes** (correto), mas as anotações de tipo ainda dizem `weakref.ref` e `weakref` é importado sem uso real (só aparece em anotação string, graças a `from __future__ import annotations`). Funcionalmente OK; só confuso/manutenível.
- **Correção sugerida:** ajustar anotação para `list[EventHandler]` e remover import `weakref` (ou usar de fato).

### 🟡 BUG-6 — Smoke test morre em console `cp1252` (emoji no rich)
- **Onde:** `scripts/smoke_test.py` (uso de 🧪 etc. no `rich`).
- **Causa:** em terminal não-UTF-8, `rich` faz `legacy_windows_render` e o emoji levanta `UnicodeEncodeError` **antes** de rodar qualquer teste → parece "1/7 fail". Sob `PYTHONIOENCODING=utf-8` passa 7/7.
- **Correção sugerida:** no topo do `smoke_test.py`, `sys.stdout.reconfigure(encoding="utf-8")` ou `Console(legacy_windows=False)`; ou evitar emoji.

---

## 4. Itens Latentes / Trabalho Futuro (não são bugs desta fase)
- **P2:** `core/agent.py` usa `MemorySaver()` (checkpointer in-memory do LangGraph) — estado de thread não persiste em Postgres. Migrar para OpenAI Agents SDK + checkpointer Postgres.
- **Latente:** `models.py` captura `EMBED_DIM` em tempo de import (`Vector(EMBED_DIM)` fixo); fica obsoleto se config muda pós-import.
- **Baixo:** `CachedEmbeddings.embed_documents` usa `uncached_indices.index(idx)` (frágil com textos duplicados).
- **Baixo:** `LongTermMemory.__init__` chama `get_settings()` duas vezes (redundante, inofensivo).

---

## 5. Conclusão
- **Fase 0 e Fase 1 estão funcionalmente verdes** nos testes automatizados (7/7 + verify_p1) e containers saudáveis.
- **Não há erros de sintaxe.**
- Foram encontrados **3 bugs de lógica reais** (BUG-1, BUG-2, BUG-3) que **quebram o agente em runtime** e/ou deixam Redis/Postgres ociosos, mais **3 de configuração/robustez** (BUG-4/5/6). BUG-1 e BUG-3 afetam o caminho real do agente e o filtro por metadata; BUG-2 impede o uso do Redis pelo `MemoryManager`. Recomenda-se corrigir BUG-1/2/3 antes de prosseguir para P2.
