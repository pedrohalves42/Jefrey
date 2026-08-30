# JEFREY-AUDIT/25_LINE_BY_LINE_SWEEP_P0-P7.md

## Varredura Linha por Linha — P0 a P7

**Data:** 2026-08-30
**Metodo:** Leitura completa de todos os arquivos .py em src/jefrey/ (40+ arquivos),
docker configs, e scripts de verificacao. Analise de: erros de logica, seguranca,
tratamento de excecoes, consistencia de patterns, correcao de metricas, isolamento
multi-tenant, thread-safety, e falsos positivos/negativos.

---

## Issues Encontrados e Corrigidos (12 fixes)

### CRITICAL (5 fixes)

| # | Arquivo | Problema | Impacto | Fix |
|---|---------|----------|---------|-----|
| C1 | `auth_middleware.py` | Comparacao `auth != f"Bearer {secret}"` vulneravel a **timing attack** — um atacante pode medir o tempo de resposta para deduzir o token byte a byte | **Seguranca**: token pode ser inferido em producao | Trocado para `hmac.compare_digest(auth, expected)` — comparacao timing-safe |
| C2 | `approvals.py` | Mesma vulnerabilidade timing attack no `_AuthMiddleware` do sub-app Starlette | **Seguranca**: igual C1 | Trocado para `hmac.compare_digest(auth, expected)` |
| C3 | `openai_agent.py` | `_guarded_call()` nao passa `user_id` no `PolicyContext` — todas as ferramentas chamadas pelo runtime OpenAI recebem `user_id="system"` | **Seguranca**: violacao de isolamento multi-tenant no provider OpenAI | Adicionado `user_id=getattr(rc, "user_id", "system")` ao PolicyContext |
| C4 | `agent.py` | `stream()` cria `AgentState` **sem `user_id=user_id`** — o LangGraph path nao propaga identidade do usuario | **Seguranca**: ferramentas executadas sem contexto de usuario | Adicionado `user_id=user_id` ao AgentState em `stream()` |
| C5 | `main.py` + `approvals.py` | `app.mount("/", approvals_app)` criava um **catch-all** no root que podia conflitar com outros routers (metrics, health, chat) | **Funcionalidade**: rotas podiam ser interceptadas pelo Starlette sub-app | Mount alterado para `/approvals`; sub-app routes ajustadas para relativas (`/pending`, `/{id}/decide`) |

### HIGH (4 fixes)

| # | Arquivo | Problema | Impacto | Fix |
|---|---------|----------|---------|-----|
| H1 | `memory.py` (endpoint) | `mm.long_term.search(q, limit=limit, ...)` — mas `PostgresLongTermMemory.search()` e `LongTermMemory.search()` nao tem parametro `limit`; o correto e `top_k` | **Bug**: endpoint `/memory/search` causaria `TypeError` em runtime | Trocado para `top_k=limit` |
| H2 | `redis_memory.py` | `health_check()` apenas chama `self._redis.ping()` — em Redis configurado com `--requirepass`, o `ping` pode funcionar sem auth em versoes antigas | **Seguranca**: health check nao valida autenticacao real | Adicionado `self._redis.echo(b"health")` que requer autenticacao |
| H3 | `auth_middleware.py` | `/metrics` **nao estava** em `_PUBLIC_PATHS` — o endpoint de Prometheus ficaria bloqueado pelo middleware de auth, impedindo o Prometheus de fazer scrape | **Observabilidade**: Prometheus nao conseguiria coletar metricas | Adicionado `/metrics` ao `_PUBLIC_PATHS` |
| H4 | `pg_memory.py` | `search()` tinha try/except interno que logava e re-levanta, e try/except externo que tambem contabilizava metricas — **double-counting** de `MEMORY_OPS` em caso de erro | **Metricas**: contadores inflados em cenarios de erro | Removido try/except interno redundante (o externo ja trata + metrica) |

### MEDIUM (3 fixes)

| # | Arquivo | Problema | Impacto | Fix |
|---|---------|----------|---------|-----|
| M1 | `config.py` | `get_settings()` singleton **nao era thread-safe** — duas threads simultaneas podiam criar duas instancias | **Concorrencia**: instancias duplicadas, waste de recursos | Adicionado `threading.Lock()` com double-checked locking |
| M2 | `db.py` | `get_engine()` e `get_session_local()` **nao eram thread-safe** — mesmo problema que M1 | **Concorrencia**: pools duplicados de conexao | Adicionado `threading.Lock()` com double-checked locking em ambos |
| M3 | `content_guard.py` | Padroes `^(Human|Assistant|System):` e `^(SYSTEM|USER|ASSISTANT):` causavam **falsos positivos** — texto normal contendo "Human:" em qualquer posicao era bloqueado | **Funcionalidade**: conteudo legitimo bloqueado desnecessariamente | Fix: `re.MULTILINE` flag + `^` so casa no inicio de linha; labels so sao perigosos no INICIO de uma linha |

---

## Nao-Erros Verificados (falsos positivos descartados)

1. **MCP client double-observe latency** — o bloco `except MCPClientError` em `call_tool()` e unreachable (nenhum codigo no try levanta MCPClientError). O bloco existe apenas como defesa. Nao causa double-counting.

2. **counted decorator raise_on_error** — o parametro `raise_on_error` controla se um warning e logado antes de re-levantar. O decorator SEMPRE re-levanta. O docstring foi revisado para refletir isso corretamente.

3. **schema.py SQL interpolation** — os nomes de tabela vem de `MEMORY_TABLES` (constante interna), nao de input do usuario. Risco SQL injection e nulo.

---

## Verificacao Pos-Fix

| Script | Resultado |
|--------|-----------|
| `verify_cipher_fixes.py` | **32/32 PASSED** |
| `verify_p7.py` | **54/54 PASSED** |
| `verify_p6.py` | **27/27 PASSED** |
| **Total** | **113/113 checks** |

Nenhum erro cascata detectado.

---

## Arquivos Modificados

1. `src/jefrey/api/auth_middleware.py` — timing-safe Bearer + /metrics publico
2. `src/jefrey/api/approvals.py` — timing-safe Bearer + mount relativo
3. `src/jefrey/api/main.py` — mount "/approvals" (nao "/")
4. `src/jefrey/api/memory.py` — top_k= em vez de limit=
5. `src/jefrey/core/openai_agent.py` — user_id no _guarded_call
6. `src/jefrey/core/agent.py` — user_id no stream()
7. `src/jefrey/core/config.py` — thread-safe singleton
8. `src/jefrey/core/db.py` — thread-safe singleton
9. `src/jefrey/core/redis_memory.py` — health_check com echo()
10. `src/jefrey/core/pg_memory.py` — simplificado search() exception path
11. `src/jefrey/core/content_guard.py` — re.MULTILINE + labels no inicio de linha

---

## Issues Deferidos (deep code review HIGH, ja documentados)

1. **Hardcoded DB password** `jefrey` — aceitavel para DEV; em producao via env var
2. **CORS `allow_headers=["*"]`** — restrito via JEFREY_API__CORS_ORIGINS em producao
3. **ChromaDB sem user_id isolation** — so afeta backend chromadb (nao postgres, que tem)
4. **Per-request agent instantiation** em chat.py — aceitavel para baixo volume
