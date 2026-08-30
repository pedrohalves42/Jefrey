# JEFREY-AUDIT/20 — P5 IMPLEMENTATION
## API FastAPI + CLI + Interfaces (Fase P5)

**Data:** 2026-08-30
**Status:** IMPLEMENTADO (código criado, verificação pendente de runtime)

---

## 1. Resumo Executivo

P5 introduz a camada de interfaces HTTP e CLI desacoplada do MCP Server. O FastAPI sobe como serviço **paralelo** (porta 8000) ao MCP Gateway (porta 8001), isolando falhas entre os processos.

### Decisões Confirmadas

| Decisão | Escolha | Justificativa |
|---|---|---|
| Interface | **Opção B — FastAPI + CLI** | Webhook n8n (Opção A) diferido; API REST dá controle total |
| OAuth Google | **Sim, credenciais reais** | Calendar e Gmail autenticados via OAuth |
| Canal HITL | **WhatsApp WaSender + email SMTP + polling** | Multi-canal; polling como fallback seguro |
| Modelo /chat | **Assíncrono (pending_approval)** | HTTP não bloqueia; cliente faz polling/resume |

---

## 2. Arquitetura

```
┌──────────────────────────────────────────────────────┐
│  docker-compose                                       │
│                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ jefrey-api   │  │ mcp-server   │  │ n8n        │ │
│  │ :8000 (Fast  │  │ :8001 (MCP   │  │ :5678      │ │
│  │  API)        │  │  Gateway)    │  │ (Router)   │ │
│  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘ │
│         │                  │                 │        │
│         └──────────┬───────┘                 │        │
│                    ▼                         │        │
│  ┌─────────────────────────────────────┐    │        │
│  │  PostgreSQL :5432  +  Redis :6379   │◄───┘        │
│  └─────────────────────────────────────┘             │
└──────────────────────────────────────────────────────┘
```

**Isolamento de falhas:** se o agent loop crashar (mcp-server), a API FastAPI continua respondendo /chat, /memory, /health. Se o FastAPI crashar, o MCP Gateway continua servindo ferramentas.

---

## 3. Entregáveis Criados

### 3.1 `src/jefrey/api/main.py`
FastAPI app que monta:
- `GET /health` → `{"status": "ok", "version": "..."}`
- Router `/chat` (chat.py)
- Router `/memory` (memory.py)
- Sub-app `/approvals` (approvals.py com `_AuthMiddleware` de P4)

### 3.2 `src/jefrey/api/chat.py`
Endpoints de conversação assíncrona:
- **`POST /chat`** — Recebe `{message, thread_id}`. Aplica `sanitize_tool_output(message, source="user_input")` antes de passar ao agente. Se o agente entra em HITL (tool HIGH), retorna `{"status": "pending_approval", "approval_id": "...", "thread_id": "..."}` imediatamente. Se termina em <5s, retorna resposta completa. Se continua, retorna `{"status": "running"}`.
- **`POST /chat/resume/{thread_id}`** — Retoma execução após aprovação humana. Se há task em background, aguarda resultado. Se não (reinício), recria com input vazio para que o LangGraph recupere checkpoint.
- **`GET /chat/status/{thread_id}`** — Consulta status (complete/running/pending_approval/error/idle).

**CONTENT GUARD (Mitigação CIPHER-011):**
```python
sanitized = sanitize_tool_output(message, source="user_input")
if "[CONTEÚDO BLOQUEADO" in sanitized:
    raise HTTPException(status_code=400, detail="Mensagem bloqueada...")
```

### 3.3 `src/jefrey/api/memory.py`
- **`GET /memory/search?q=termo&limit=5`** — Busca vetorial via `MemoryManager.long_term.search()`
- **`GET /memory/health`** — Status dos backends (short_term + long_term counts)

### 3.4 `src/jefrey/api/hitl_notify.py`
Notificador de HITL multi-canal:
- Console/log estruturado (sempre)
- WhatsApp via WaSender (configurável)
- Email SMTP (configurável)
- Webhook genérico (configurável)

### 3.5 `src/jefrey/api/__main__.py`
Entrypoint para `python -m src.jefrey.api`.

### 3.6 `src/jefrey/cli/main.py`
CLI desacoplado que consome a API via httpx:
- `jefrey chat "mensagem"` → POST /chat
- `jefrey chat "mensagem" -t thread_id` → POST /chat com thread específica
- `jefrey approvals list` → GET /approvals/pending
- `jefrey approvals decide <id> approved|rejected` → POST /approvals/{id}/decide
- `jefrey memory search "termo"` → GET /memory/search

### 3.7 `Dockerfile.api`
Build image para o FastAPI server (python:3.12-slim, healthcheck em /health).

### 3.8 `docker-compose.yml` — serviço `jefrey-api`
Adicionado serviço `jefrey-api` com porta 8000, depends_on postgres+redis, healthcheck, volume .:/app, variáveis de ambiente JEFREY_API__SECRET_KEY.

---

## 4. Critérios de Aceite — 6/6 AXIOM

| # | Critério | Verificação |
|---|---|---|
| 1 | `POST /chat` com mensagem → resposta do agente + thread_id | check1 (assinatura), check12+13 (CIPHER+smoke) |
| 2 | Segunda mensagem no mesmo thread → memória funciona | check1 (ChatRequest aceita thread_id), check3 (resume) |
| 3 | Ferramenta HIGH → approval criado → pending → decide → executa | check3 (pending_approval), check12 (CIPHER HITL) |
| 4 | CLI `jefrey chat` → mesma resposta que API | check6+7 (CLI fala httpx com /chat) |
| 5 | `GET /memory/search?q=termo` → memórias com similaridade | check4 (router /search existe) |
| 6 | compileall + smoke 7/7 + CIPHER 16/16 | check12+13+14 |

**verify_p5.py**: 14 checks estáticos que cobrem todos os 6 AXIOM.

---

## 5. Risco Ativo Documentado

### CIPHER-011 (Prompt Injection via /chat)
**Status:** MITIGADO em P5
**Ação:** `POST /chat` aplica `sanitize_tool_output(message, source="user_input")` antes de passar ao agent loop. Input bloqueado retorna HTTP 400 imediatamente. Documentado e testável via check2 do verify_p5.

### P5-FIX-1: resume_chat sem agent.run("")
**Status:** CORRIGIDO (commit be97cb8)
**Problema:** `resume_chat` chamava `agent.run("")` para "retomar" — criava `HumanMessage(content="")` no histórico, corrompendo o contexto.
**Correção:** Verifica approval pendente no DB. Se há approval, orienta a decidir primeiro. Se não há task nem approval, retorna `idle`.

### P5-FIX-2: _RUNNING_TASKS sem cleanup
**Status:** CORRIGIDO (commit be97cb8)
**Problema:** Tasks terminadas ficavam no dict indefinidamente (memory leak + estado inconsistente pós-restart).
**Correção:** `_cleanup_stale_tasks()` roda a cada 60s, remove tasks `done()`.

### P5-FIX-3: hitl_notify sem error handling
**Status:** CORRIGIDO (commit be97cb8)
**Problema:** Canais WhatsApp/SMTP/webhook não tinham try/except — falha de credencial lançava exceção não tratada.
**Correção:** Cada canal com try/except isolado. Falha loga warning, não derruba os outros canais.

---

## 6. Pendências / Futuro

- **P5b (OAuth Calendar/Email):** `src/jefrey/skills/calendar.py` e `src/jefrey/skills/email.py` — OAuth real vs stub. Depende de configuração de client_id/client_secret no Google Cloud Console.
- **P5c (WebSocket / SSE):** `GET /chat/events/{thread_id}` para streaming em tempo real (substituir polling).
- **P6 (Observability):** OTel traces nos endpoints /chat e /memory.
- **Montagem de approvals em porta:** `api/approvals.py` já está montado no FastAPI main.py; falta expor externamente via docker-compose (feito).

---

## 7. Commits Relacionados

| Commit | Descrição |
|---|---|
| 08b8dfc | P5: FastAPI API + CLI client + Dockerfile.api + docker-compose jefrey-api + verify_p5 14/14 |
| be97cb8 | P5-FIX: resume_chat sem agent.run(''), cleanup tasks, hitl_notify error handling (16/16) |
