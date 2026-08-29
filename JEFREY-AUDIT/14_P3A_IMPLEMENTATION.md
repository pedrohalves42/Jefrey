# 14 — P3a: MCP Gateway (servidor dedicado, streamable-http :8001)

**Data:** 2026-08-28 · **Autor:** AXIOM · **Status:** ✅ 100% — IMPL + TESTE + SEG + OBS + DOC + CRITÉRIO DE ACEITE

Implementação do **P3a**: Jefrey expõe suas ferramentas via MCP como **processo separado**
(FastMCP/MCPServer do SDK `mcp` 2.x) em transporte `streamable-http` na porta 8001. Cada
ferramenta passa obrigatoriamente pelo `PolicyEngine` antes de executar, com `thread_id`
vindo do request MCP (não hardcoded), para rastrear no audit log qual workflow do n8n chamou
qual ferramenta.

---

## Decisões fechadas (input do usuário)

- **Modo de política:** manter `enforce` (default) em P3. Para rodar HIGH em dev, usar
  `user_role=admin` (bypass já implementado) — não relaxar o modo global. (Opção B.)
- **Arquitetura:** **processo separado** (Uvicorn/anyio dedicado). Motivo: chamadas do n8n
  podem ser lentas (busca, calendar, email); se no mesmo loop do agente, bloqueariam o agente.
- **Riscos 2/3/4 aceitos como débito técnico documentado:** `_save` sem try/except → P4;
  `WindowsSelectorEventLoopPolicy` deprecia em 3.16 (migração Linux/prod); `approvals`
  acumulando `pending` → cleanup no teardown do verify (feito).

---

## BUG encontrado e corrigido (BUG-P3a-01)

**Bug silencioso descoberto durante P3a** — exatamente a classe de quebra que o pré-P3 queria evitar:

`PolicyEngine.risk_of()` classificava risco por **prefixo de nome** (`notes_*`, `web_search*`,
`automation_*`). Porém as ferramentas do `SkillRegistry` são nomeadas por **função**
(`save_note`, `search_notes`, `create_workflow`, `extract`, `plan_task`, `run_workflow`, …),
que NÃO seguem esses prefixos. Resultado: **todas as 15 ferramentas reais caíam em
`desconhecido → HIGH`** e seriam **bloqueadas em modo `enforce`** — o gateway barraria
todas as ferramentas legítimas.

**Correção:** `risk_of()` reclassificado por semântica:
- `LOW`: leitura/busca/memória (`note`, `search`, `memory`, `notes_`, `web_search`, `memory_search`)
- `MEDIUM`: automação/workflow/deleção (`workflow`, `plan_`, `extract`, `automation_`, `delete_*`, `notes_delete`)
- `HIGH`: `email_`/`calendar_`/`gmail_` + substrings destrutivas (`rm_rf`, `shell_exec`, …) + desconhecido (fail-safe)

Fixo durável (risco **declarado por ferramenta** na skill, em vez de heurística de nome) fica para **P4**.
`verify_p2`/`verify_p3_pre` continuam verdes (email_send/rm_rf_everything seguem HIGH; memory_search/web_search LOW).

---

## Arquivos

| Arquivo | Ação | Conteúdo |
|---|---|---|
| `src/jefrey/mcp/__init__.py` | criado | re-exporta `build_server`, `main` |
| `src/jefrey/mcp/server.py` | criado | `MCPServer` (mcp 2.x), registra SkillRegistry + 2 tools HIGH de integração, rota `/health`, guarda cada tool via PolicyEngine |
| `src/jefrey/mcp/__main__.py` | criado | entrypoint `python -m src.jefrey.mcp` |
| `src/jefrey/core/config.py` | editado | `MCPServerSettings` (`JEFREY_MCP__HOST/PORT/TRANSPORT/PATH`) + campo `mcp` em `AppSettings` |
| `src/jefrey/core/policy.py` | editado | `risk_of()` reclassificado (BUG-P3a-01); `audit()` agora loga `reason` (admin_bypass visível) |
| `scripts/verify_p3a.py` | criado | sobe servidor em processo separado, testa LOW/HIGH/user/HIGH/admin via transporte real |
| `docker-compose.yml` | editado | serviço `mcp-server` (healthcheck `/health`, depende de postgres/redis) — sem n8n |
| `requirements.txt` | editado | `mcp>=1.19.0,<3` |

**Nota — FastMCP vs MCPServer:** em `mcp>=2` a classe high-level chama-se `MCPServer`
(`FastMCP` era o nome da v1). `openai-agents` exige `mcp<3,>=1.19.0`, então usamos o SDK já
instalado (2.1.1) sem downgrade (evita regressão em P2). Funcionalmente é o FastMCP equivalente.

**Nota — tools de integração HIGH (stubs):** `email_send`/`calendar_create` são expostos como
ferramentas HIGH com implementação stub (`{"executed": true, ...}`); envio/OAuth reais em **P5**.
Isso permite exercitar o caminho HIGH sob PolicyEngine (bloqueio p/ user, execução p/ admin) no gateway.

---

## Critério de aceite AXIOM — P3a

| # | Critério | Resultado |
|---|----------|-----------|
| 1 | Tool LOW via MCP → resultado correto + audit log | ✅ `save_note` executa (`"saved": true`), audit `decision=allow` |
| 2 | Tool HIGH via MCP → bloqueada + approval no Postgres + audit log | ✅ `email_send` bloqueada, approval persistido, audit `decision=deny` |
| 3 | Tool HIGH + `user_role=admin` → executa + audit `admin_bypass` | ✅ `email_send` admin executa (`"executed": true`), audit `decision=allow reason=admin bypass` |
| 4 | `verify_p3a.py` idempotente (3 execuções) | ✅ 3/3 passam; approvals limpos no teardown |
| 5 | `/health` disponível no MCP Server | ✅ `GET /health` → `{"mcp":"ok","status":"healthy","tools":17,...}` |
| 6 | `compileall` exit 0 + sem regressão smoke/p1/p2 | ✅ compileall=0; smoke 7/7, P1 ✅, P2 ✅ |

**Total: 6/6 verde.**

---

## Como executar

```bash
# Servidor (processo separado)
python -m src.jefrey.mcp            # ou: docker compose up mcp-server

# Verificação
python scripts/verify_p3a.py
```

Cliente MCP (ex.: n8n) conecta em `http://localhost:8001/mcp`. Toda chamada deve trazer
`thread_id` (e opcionalmente `user_role`); o PolicyEngine decide com esse `thread_id`.

---

## Próximo (P3b/P3c)
- P3b: n8n no compose + workflow "roteador de eventos genérico" ponte Jefrey↔n8n.
- P3c: Jefrey como MCP Client (consumir ferramentas externas via MCP).
- P4: risco por ferramenta declarado na skill; HITL UI; input/output guardrails.
