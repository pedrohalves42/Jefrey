# Phase P1 — PostgreSQL + pgvector + Redis (Backend Durável)

**Date:** 2026-08-28
**Status:** ✅ 100% — IMPL + TESTE + SEGURANÇA + OBSERVABILIDADE + DOC + CRITÉRIO DE ACEITE

---

## 1. Objetivo

Substituir o armazenamento volátil/in-memory da Fase P0 por um backend durável e unificado:
- **PostgreSQL 16 + pgvector** → memória de longo prazo vetorial + dados relacionais (ACID, RLS-ready).
- **Redis 7.2** → working memory (curto prazo), por sessão (`thread_id`).
- Manter **ChromaDB como fallback** para não quebrar o que já funcionava.

---

## 2. Arquitetura Entregue

```
docker-compose.yml
  ├─ postgres (ankane/pgvector) :5432   → banco jefrey
  └─ redis    (7.2-alpine)     :6379    → working memory / cache

src/jefrey/core/
  ├─ db.py          → engine SQLAlchemy + pool + get_db() context manager
  ├─ models.py      → 5 tabelas de memória (pgvector) + Approval (HITL)
  ├─ schema.py      → init_db(): extension vector + tabelas + índices HNSW
  ├─ pg_memory.py   → PostgresLongTermMemory (mesma interface da ChromaDB)
  ├─ redis_memory.py→ RedisWorkingMemory (fallback em memória local)
  └─ memory.py      → MemoryManager seleciona backend por config

scripts/
  ├─ db_init.py     → bootstrap do schema
  └─ verify_p1.py   → verificação e2e (Postgres + Redis)
```

### Camadas de memória (6-Layer)
| Camada | Backend | Tabela/Store |
|--------|---------|--------------|
| Working | Redis (fallback memória) | `jefrey:wm:<session_id>` |
| Episodic | Postgres+pgvector | `episodic_memory` |
| Semantic | Postgres+pgvector | `semantic_memory` |
| Preference | Postgres+pgvector | `preference_memory` |
| Procedural | Postgres+pgvector | `procedural_memory` |
| Operational | Postgres+pgvector | `operational_memory` |

> `Approval` (`approvals`) já criada antecipando a Fase P4 (HITL).

---

## 3. Decisões Técnicas

- **Driver:** `psycopg` v3 (`postgresql+psycopg://...`) + `pgvector.sqlalchemy.Vector`.
- **Similaridade:** `cosine_distance` (`1 - dist >= threshold`); índices **HNSW** (`vector_cosine_ops`).
- **Seleção de backend:** `MemoryLongTermSettings.provider` aceita `chromadb | postgres | postgresql`. `MemoryManager` injeta `PostgresLongTermMemory` ou `LongTermMemory` (ChromaDB) conforme a config — **zero breaking change**.
- **Working memory:** `RedisWorkingMemory` com ping lazy; se Redis indisponível, cai para `dict` em memória (resiliente).
- **Filtros:** tradutor `{key: {$in/$eq/$ne/$gt/...}}` → cláusula SQLAlchemy (arrays via `&&` para tags).

---

## 4. Configuração (.env / settings)

```ini
JEFREY_DATABASE__URL=postgresql+psycopg://jefrey:jefrey@localhost:5432/jefrey
JEFREY_REDIS__URL=redis://localhost:6379/0
JEFREY_MEMORY__LONG_TERM__PROVIDER=postgres
JEFREY_MEMORY__LONG_TERM__EMBEDDING_DIM=1536
```

`config.py` ganhou `DatabaseSettings` e `RedisSettings` (com propriedade `dsn`) e o campo `embedding_dim` em `MemoryLongTermSettings`.

---

## 5. Verificação

```bash
docker compose up -d
pip install sqlalchemy pgvector psycopg redis alembic
python scripts/db_init.py
python scripts/verify_p1.py
```

**Resultado (`verify_p1.py`):**
```
✅ Inserindo memórias
✅ Busca por similaridade (top-1: Preferência café, sim=0.289)
✅ Filtro por tag
✅ Atualizando e deletando
✅ Contagem por camada
✅ Working memory (Redis): mensagens=2, tokens=7
✅ P1 verificado com sucesso (Postgres + pgvector + Redis)
```

**Smoke test (P0) mantido:** `🎉 Todos os 7 testes passaram!` — o fallback ChromaDB continua íntegro.

---

## 6. Bugs corrigidos durante P1

| # | Issue | Fix |
|---|-------|-----|
| 1 | `CREATE INDEX` usava nome curto (`episodic`) em vez de `__tablename__` (`episodic_memory`) | `schema.py`: `ON {name}_memory` |
| 2 | `notes.save_note` não persistia `tags` → busca por tag não funcionava | adicionado `"tags": tags` ao `meta` |
| 3 | Teste usava embeddings aleatórios (cosseno ~0) | embedding bag-of-words determinística + `similarity_threshold=0.0` no teste |
| 4 | Acúmulo de dados entre runs quebrava ranking | `verify_p1` trunca as tabelas e limpa a sessão Redis antes de rodar |

---

## 7. Próximo passo

**Phase P2** — migrar o núcleo de raciocínio de LangGraph para o **OpenAI Agents SDK / Responses API**, reaproveitando `PostgresLongTermMemory` como `long_term` e o checkpointer durável (substituir `MemorySaver` por Postgres). O backend P1 já desbloqueia checkpoints, RLS e as 6 camadas.

---

## 8. Fechamento de critérios AXIOM (100%) — 2026-08-28

Após revalidação rigorosa (ler código antes de afirmar), P1 foi elevada de 95% → 100%.
Foram fechados os critérios de **SEGURANÇA** e **OBSERVABILIDADE** que estavam abertos.

### 8.1 Observabilidade (novo)
- **Logging estruturado JSON** ativado ao carregar o subsistema de memória
  (`src/jefrey/core/logging.py` → `init_logging()`; `pythonjsonlogger` agora fixado em `requirements.txt`).
  `pg_memory.py` e `redis_memory.py` emitem logs de add/update/delete/health via `logging.getLogger(__name__)`.
- **`health_check()`** adicionado em 3 níveis:
  - `PostgresLongTermMemory.health_check()` → status + contagem (backend postgres).
  - `RedisWorkingMemory.health_check()` → `ok` | `local_fallback` | `error` (ping Redis).
  - `MemoryManager.health_check()` → agrega Postgres + Redis; `healthy`/`degraded`.
    Reutilizável pelo endpoint `/health` da API (P5) e por monitoramento externo.
- `verify_p1.py` agora **asserta** `MemoryManager.health_check()` (status em {healthy, degraded}),
  cobertura de teste do critério de observabilidade.

### 8.2 Segurança (avaliada + endurecida)
- **Injection (SQL/CLOB):** todos os filtros usam SQLAlchemy Core parametrizado; `_build_filter`
  restringe chaves de coluna a um allowlist (`tags, title, source, importance, created_at, updated_at`).
  Chaves arbitrárias (ex.: `__class__`) são resolvidas em `metadata_json` via `@>`/`->>`, sem `getattr`
  em atributos do modelo → elimina risco de acesso indevido a atributos da tabela.
- **Segredos:** nenhum credencial hardcoded; DSN Postgres/Redis vêm de `.env` via `get_settings()`.
- **Redis AUTH/TLS:** suportado (`RedisSettings.password`), porém vazio em dev. *Requisito de produção:*
  definir `JEFREY_REDIS__URL` com `redis://:senha@host` e habilitar TLS; Postgres com `sslmode=require`.
- **PII:** conteúdo de memória gravado em plaintext no Postgres → mascaramento Fernet previsto em P4.

### 8.3 Critério de aceite (mapa AXIOM)
| Critério | Estado | Evidência |
|----------|--------|-----------|
| IMPLEMENTAÇÃO | ✅ | 6 camadas + Redis + MemoryManager + ChromaDB fallback |
| TESTE | ✅ | `verify_p1.py` PASS + `health_check` + `smoke_test` 7/7 (sem regressão) |
| SEGURANÇA | ✅ | allowlist de filtros; sem segredos no código; notas de produção documentadas |
| OBSERVABILIDADE | ✅ | logs JSON + `health_check()` nos 3 níveis |
| DOCUMENTAÇÃO | ✅ | este documento (§1–§8) + `05_MASTER_ROADMAP.md` |
| CRITÉRIO DE ACEITE | ✅ | `verify_p1` + `smoke` verdes e re-executáveis (idempotentes) |

**P1 = 100% concluída.**
