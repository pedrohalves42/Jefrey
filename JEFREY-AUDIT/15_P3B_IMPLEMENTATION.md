# 15 — P3b: n8n Event Router (ponte Jefrey↔n8n via MCP)

**Data:** 2026-08-29 · **Autor:** AXIOM · **Status:** ✅ 100% — IMPL + TESTE + SEG + OBS + DOC + CRITÉRIO DE ACEITE

Implementação do **P3b**: o n8n (no compose, `:5678`) recebe eventos via Webhook
`/webhook/jefrey-events`, roteia por `event_type` (Switch) e chama o **Jefrey MCP Server**
(`mcp-server:8001`, streamable-http) como **MCP Client** falando JSON-RPC puro. Cada
ferramenta passa pelo `PolicyEngine` (LOW executa; HIGH user é bloqueado + cria approval;
HIGH `admin` faz bypass). O webhook retorna `result + thread_id + event_type + audit_id + statusCode`.

---

## Decisões fechadas (input do usuário + descobertas em P3b)

- **n8n como MCP Client → Jefrey MCP Server** (transporte `streamable-http`, `Accept: application/json`).
- **Modo de política:** mantido `enforce`. HIGH `user` → bloqueado (autônomo, sem humano); HIGH `admin` → bypass.
- **Stateless HTTP no MCP Server** (`stateless_http=True`): cada request cria transporte fresco, sem
  obrigatoriedade de `Mcp-Session-Id` nem do handshake `initialize` prévio. **Decisão central de P3b** —
  elimina toda a fiação de sessão que quebrava o n8n (o Code node do n8n não tem `fetch`/`require` e o
  HTTP Request node não expunha o session id). Com stateless, o n8n faz **um único POST `tools/call`**.
- **HTTP Request nodes (não Code node com `fetch`)**: o Code node do n8n roda sem sandbox de rede
  (`fetch`/`require` indisponíveis); portanto a chamada MCP é feita por **HTTP Request nodes** (determinístico,
  sem parse de SSE). O Code node é usado apenas para *montar o payload* JSON-RPC e *parsear a resposta*.

---

## BUGs encontrados e corrigidos durante P3b

### BUG-P3b-01 — Webhook retornava corpo vazio (integração n8n→MCP quebrada)
O workflow original usava um **Code node com `fetch`** (indisponível no n8n) → corpo vazio.
**Correção:** reescrito para **HTTP Request node** (`specifyBody: "json"` + `contentType: "json"` +
`jsonBody: ={{ $json.body }}`). Testado empiricamente: `save_note` executa, `email_send` HIGH bloqueia
com `approval_id`, HIGH `admin` bypass.

### BUG-P3b-02 — `PolicyEngine` não emitia `approval_id` no bloqueio
`_run_guarded` retornava só `res.reason`. Como o approval é criado em `_hitl`, o id ficava oculto na resposta.
**Correção:** `server.py` agora inclui `approval_id` na mensagem de DENY quando presente → webhook retorna
`[BLOQUEADO PELA POLÍTICA] ... (thread=...; approval_id=uuid)`.

### BUG-P3b-03 — `save_note` falhava validação de `tags` (`_type_name` não tratava `X | None`)
`_type_name(ann)` retornava `"str"` para qualquer `list[str] | None` (o `get_origin` de uma `Union` é
`UnionType`, não `list`), gerando schema MCP errado (`tags: string`) → erro "Input should be a valid string".
**Correção:** `_type_name` agora **desempacota `Optional[X]`** antes de classificar o tipo. `save_note` (LOW)
passa a executar com `tags` como lista.

### BUG-P3b-04 — Switch V3 (n8n 2.36) não roteava
`fallbackOutput: 2` (número, top-level) está errado; V3 exige `options.fallbackOutput: "extra"` (cria a
saída fallback no índice `rules.values.length`). Além disso faltava `combinator` no `conditions` e o
`operator` estava como `{type:"stringEquals"}` (correto: `{type:"string", operation:"equals"}`).
**Correção:** nó Switch reescrito com a forma exata da V3.

### BUG-P3b-05 — HTTP Request V3 param names
Usava `specification:"body"` / `bodyContentType:"json"`. Correto em V3: **`specifyBody:"json"`** e
**`contentType:"json"`** (lidos como `getNodeParameter('specifyBody'/'contentType')`). Sem isso o corpo
nunca era enviado (`{'': ''}` → MCP rejeitava).

### BUG-P3b-06 — Embeddings (Ollama) inalcançáveis DENTRO do container Docker
`save_note` falhava com "Failed to connect to Ollama" porque `JEFREY_EMBEDDINGS__BASE_URL=localhost:11434`
resolve para o container, não a host. **Correção:** `docker-compose.yml` do `mcp-server` agora aponta
`JEFREY_EMBEDDINGS__BASE_URL: http://host.docker.internal:11434` (testado: 200 OK de dentro do container).
> Observação: `host.docker.internal` é específico de Docker Desktop (Windows/Mac). Em Linux, usar o gateway
> do host. Documentado para produção.

### BUG-P3b-07 — `memory_search` não registrado (nome semântico ≠ ferramenta real)
O roteamento `memory_query` apontava para `memory_search`, mas a ferramenta registrada no MCP Server é
`search_notes` (do `SkillRegistry`). **Correção:** `Build MCP Payload` mapeia `memory_query → search_notes`
(o `PolicyEngine` ainda classifica ambos como LOW). Resultado: `memory_query` executa e retorna `[]`/resultados.

---

## Arquivos

| Arquivo | Ação | Conteúdo |
|---|---|---|
| `n8n/workflows/jefrey-event-router.json` | reescrito | Webhook → Switch (rules V3) → Build MCP Payload (Code) → Call Jefrey MCP (HTTP Request, stateless) → Parse MCP Response (Code) → Respond. Fallback 400. |
| `src/jefrey/mcp/server.py` | editado | `run(..., stateless_http=cfg.stateless_http)`; `_run_guarded` inclui `approval_id` no DENY; `_type_name` desempacota `Optional`. |
| `src/jefrey/core/config.py` | editado | `MCPServerSettings.stateless_http: bool = True` (+ doc). |
| `docker-compose.yml` | editado | `mcp-server` env: `JEFREY_EMBEDDINGS__BASE_URL: http://host.docker.internal:11434`. |
| `scripts/verify_p3b.py` | criado | sobe/aguarda compose, deploy idempotente do workflow (find-or-delete + import + activate via REST), 5 casos de webhook × 3 iterações, approval no Postgres, compileall, smoke 7/7, P1/P2/P3a sem regressão. |
| `scripts/verify_p3a.py` | editado | reutiliza servidor já em execução (Docker :8001) em vez de sempre spawnar; captura logs do container para os checks de audit. |

---

## Critério de aceite AXIOM — P3b

| # | Critério | Resultado |
|---|----------|-----------|
| 1 | n8n saudável (`/healthz`) + workflow persistido (volume) | ✅ `healthz=200`; workflow versionado em `n8n/workflows/` e ativo no n8n. |
| 2 | Webhook roteia por `event_type` (Switch: `tool_call`/`memory_query`/fallback) | ✅ `tool_call`→Build→MCP; `memory_query`→Build→MCP (`search_notes`); evento desconhecido→`400`. |
| 3 | Tool **LOW** via webhook executa | ✅ `save_note` → `{"saved": true, ...}` (com embeddings Ollama via `host.docker.internal`). |
| 4 | Tool **HIGH** via webhook bloqueado **+ approval** | ✅ `email_send` user → `[BLOQUEADO...] ... approval_id=<uuid>`; approval persistido no Postgres. |
| 5 | Tool **HIGH** + `user_role=admin` executa (bypass) | ✅ `email_send` admin → `{"executed": true, ...}`. |
| 6 | `verify_p3b.py` idempotente (3×) + `compileall`=0 + smoke 7/7 + P1/P2/P3a sem regressão | ✅ 3/3 iterações verdes; compileall=0; smoke 7/7; verify_p1/p2/p3a = 0 (sem regressão). |

**Total: 6/6 verde** (validado por `python scripts/verify_p3b.py`).

---

## Observações de segurança / operacionais

- **Stateless**: cada request é um transporte novo — adequado para webhooks e escala horizontal (sem afinidade
  de sessão). Clientes MCP completos (verify_p3a / openai-agents) continuam funcionando (initialize+tools/call
  também aceitos em modo stateless).
- **Política em `enforce`**: em modo autônomo, HIGH sem humano é **bloqueado por design** (não executa). O
  pedido fica registrado na tabela `approvals` (HITL futuro em P4/P5).
- **n8n auth**: owner + cookie de sessão (User Management 2.36); a API REST de workflows usa o cookie de sessão
  (os `scopes` da API key são restritos por role no 2.36 — cookie é o caminho confiável para deploy via script).
- **Ollama em Docker**: `host.docker.internal` exige Docker Desktop; ajustar para Linux em produção.

---

## Como executar

```bash
# Stack completo (já em execução neste ambiente)
docker compose up -d

# Verificação ponta-a-ponta (idempotente, 6/6 + regressão)
python scripts/verify_p3b.py
```

Teste manual rápido do webhook:
```bash
curl -s -X POST http://localhost:5678/webhook/jefrey-events \
  -H 'Content-Type: application/json' \
  -d '{"event_type":"tool_call","thread_id":"t1","user_role":"user",
       "payload":{"tool":"save_note","args":{"title":"x","content":"y","tags":["z"]}}}'
# -> {"result":"{\"id\":...\"saved\": true...}","thread_id":"t1",...,"statusCode":200}
```

---

## Próximo (P3c / P4)

- **P3c**: Jefrey como **MCP Client** (consumir ferramentas externas via MCP).
- **P4**: risco **declarado por ferramenta** na skill (elimina heurística de nome); **HITL UI** para aprovar
  `approvals`; input/output guardrails; `host.docker.internal` → config de produção.
