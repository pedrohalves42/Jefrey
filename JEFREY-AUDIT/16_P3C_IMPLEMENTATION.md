# 16 — P3c: Jefrey como MCP Client (consumo de servidores MCP externos)

**Data:** 2026-08-29 — **Autor:** AXIOM — **Status:** ✅ 100% — IMPL + TESTE + SEG + OBS + DOC + CRITÉRIO DE ACEITE

Implementação do **P3c**: o Jefrey vira **MCP Client** capaz de consumir ferramentas de servidores
MCP **externos**, fechando o lado inverso do gateway MCP (P3a/P3b = Jefrey como MCP Server). O módulo
`src/jefrey/mcp/client.py` (`MCPClient`) suporta os transportes **stdio** (subprocesso spawnado) e
**streamable-http**, normaliza o `CallToolResult` em texto e é construído a partir de specs de configuração.

Alvo arquitetural (Decisão 1 = Opção C): **Jefrey → MCPClient → n8n MCP Server → workflows**.

---

## Decisões fechadas (input do usuário + descobertas em P3c)

- **Decisão 1 → Opção C**: Jefrey consome ferramentas MCP externas via `MCPClient`. O alvo é o **MCP Server
  do n8n**; o cliente é genérico (qualquer servidor MCP compatível funciona, inclusive o próprio Jefrey MCP
  Server em `localhost:8001`). Rejeitada a Opção A (loopback no próprio server) por redundância.
- **Decisão 2 → Módulo isolado**: `MCPClient` é um **utilitário testável, FORA do loop de raciocínio do
  agente (LangGraph/OpenAI)**. A integração no agent loop (quando o agente decidir chamar uma ferramenta MCP
  externa durante o raciocínio) fica para **P4**, que refatora o loop de qualquer forma (RBAC, HITL UI). Fazer
  agora seria refactor descartável. As duas decisões são compatíveis (Opção C = *o quê*; Decisão 2 = *quão
  acoplado agora*).
- **Transports**: `streamable-http` (`streamable_http_client`, aceita 2 ou 3 tuplas conforme a versão do SDK)
  e `stdio` (`stdio_client` + `StdioServerParameters`, `env=None` herda `os.environ` do pai).

---

## BUGs encontrados e corrigidos durante P3c

### BUG-P3c-01 — `streamable_http_client` retorna 2 valores (não 3) nesta versão do SDK
O código original fazia `read, write, _ = await streamable_http_client(url)` e quebrava com
`not enough values to unpack (expected 3, got 2)`. **Correção:** `streams = await ...; read, write = streams[0], streams[1]` (tolerante a 2 ou 3).

### BUG-P3c-02 — `Tool` usa `input_schema` (snake_case), não `inputSchema`
`list_tools` acessava `t.inputSchema` → `AttributeError: 'Tool' object has no attribute 'inputSchema'. Did you mean: 'input_schema'?`. **Correção:** `t.input_schema`.

### BUG-P3c-03 — `from_spec` chamava `.get()` num modelo pydantic
`spec.get("command")` levantava `AttributeError` porque `ExternalMCPServer` (pydantic) não tem `.get`. **Correção:** helper `_get(spec, key)` que lê via `getattr` (modelo) ou `.get` (dict).

### BUG-P3c-04 — `_spec_env` era `@staticmethod` mas usava `cls`
`NameError: name 'cls' is not defined`. **Correção:** `_spec_env` promovido a `@classmethod`.

### BUG-P3c-05 — `check()` quebrava em codepage cp1252 ao imprimir `✅`/`❌`
Quando o stdout é um pipe/console cp1252 (sem `PYTHONIOENCODING=utf-8`), o `print("✅ ...")` levantava
`UnicodeEncodeError` e abortava o verify. **Correção:** `verify_p3c.py` faz `sys.stdout/stderr.reconfigure(encoding="utf-8", errors="replace")` no topo; execução com `PYTHONIOENCODING=utf-8` (propaga ao subprocesso `verify_p3b`).

---

## Arquivos

| Arquivo | Ação | Conteúdo |
|---|---|---|
| `src/jefrey/mcp/client.py` | criado | `MCPClient` (stdio + streamable-http), `list_tools`, `call_tool`, `from_spec`, `_result_to_text`. `MCPClientError`. |
| `src/jefrey/core/config.py` | editado | `ExternalMCPServer` + `MCPClientSettings` (`JEFREY_MCP_CLIENT__`); `AppSettings.mcp_client`. |
| `scripts/mcp_external_demo_server.py` | criado | Servidor MCP externo REAL (stdio, high-level `MCPServer`) expondo `add`/`echo`/`jefrey_ping` — alvo da prova end-to-end (não é loopback). |
| `scripts/verify_p3c.py` | criado | conecta via stdio no demo server e executa ferramentas; conecta via http no Jefrey MCP Server (`:8001`); valida config; `compileall`; smoke 7/7; regressão `verify_p3b` (cobra P1/P2/P3a). |
| `scripts/verify_p3b.py` | (inalterado) | reutilizado como gate de regressão em P3c. |

---

## Critério de aceite AXIOM — P3c

| # | Critério | Resultado |
|---|----------|-----------|
| 1 | `MCPClient` (stdio) conecta servidor MCP externo real e **lista** ferramentas | ✅ `['add','echo','jefrey_ping']` |
| 2 | `MCPClient` (stdio) **executa** ferramentas externas com resultado correto | ✅ `add(2,3)='5'`, `echo('hi')='hi'`, `jefrey_ping()='pong'` |
| 3 | `MCPClient` (streamable-http) conecta servidor MCP externo real e lista ferramentas | ✅ 17 ferramentas no `localhost:8001/mcp` (Jefrey MCP Server) |
| 4 | Config `MCPClientSettings` + `ExternalMCPServer` parseiam via env e `from_spec` cria o cliente | ✅ http (`url`) e stdio (`command`) OK |
| 5 | Módulo **isolado** (fora do agent loop LangGraph) — por design, não acoplado | ✅ nenhum import de `agent`/`langgraph` no `client.py` |
| 6 | `verify_p3c.py` idempotente + `compileall`=0 + smoke 7/7 + sem regressão P1/P2/P3a/P3b | ✅ 12/12 checks; `verify_p3b rc=0` |

**Total: 6/6 verde** (validado por `python scripts/verify_p3c.py` → `EXIT=0`, `12 passou, 0 falhou`).

---

## Observações de segurança / operacionais

- **Módulo isolado**: `MCPClient` é um utilitário; ele **não** está no loop de raciocínio do agente. Chamadas
  externas hoje são explícitas (código/verify). A integração no agent loop (ferramenta "mcp_call" exposta ao
  LLM) é P4 — altura em que o `PolicyEngine` poderá inspecionar também chamadas *de saída* (Jefrey→externo).
- **Superfície de ataque externa**: quando P4 ligar o cliente ao agent loop, chamar servidores MCP arbitrários
  (ex.: n8n) introduz confiança em terceiros. Recomenda-se allowlist de servidores (`MCPClientSettings.servers`)
  e, se a ferramenta for de risco, passar pelo `PolicyEngine` (hoje o `client.py` não impõe política — é
  transporte puro, propositalmente).
- **stdio**: `env=None` herda o ambiente do pai; para servidores que precisam de `host.docker.internal` ou
  credenciais, passar `env` explícito via `ExternalMCPServer.env` (ou injeção no `command`).
- **Windows/anyio**: encerramento de `stdio_client` pode emitir ruído de cancel-scope no shutdown (conhecido no
  anyio/Windows); não afeta a funcionalidade (verificado: `FIM` impresso, resultados corretos).

---

## Como executar

```bash
# Stack já em execução (postgres/redis/mcp/n8n healthy)
docker compose up -d

# Verificação ponta-a-ponta (idempotente, 12/12 + regressão)
set PYTHONIOENCODING=utf-8
python scripts/verify_p3c.py
```

Teste manual rápido do cliente (stdio → servidor demo):
```bash
python -c "
import asyncio, sys
from src.jefrey.mcp.client import MCPClient
async def t():
    async with MCPClient(command=[sys.executable, 'scripts/mcp_external_demo_server.py']) as c:
        print(await c.list_tools())
        print(await c.call_tool('add', {'a': 2, 'b': 3}))
asyncio.run(t())
"
```

---

## Próximo (P4)

- **P4**: Integrar `MCPClient` ao **agent loop** (ferramenta `mcp_call` exposta ao LLM, com `PolicyEngine` para
  chamadas de saída), **RBAC** admin/user/guest, **HITL UI** para aprovar a tabela `approvals`, guardrails de
  input/output, e risco **declarado por ferramenta** na skill (elimina heurística de nome).
- Opcional P3c.2: apontar `MCPClientSettings.servers` para o **MCP Server do n8n** (quando o n8n expuser o
  endpoint) e prover a cadeia completa Jefrey → n8n MCP Server → workflows (o cliente já está pronto para isso).
