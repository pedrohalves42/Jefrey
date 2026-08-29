# 17 — CIPHER: Revisão de Segurança/Qualidade e Remediação

**Status:** ✅ Remediação BLOCOS 1–4 CONCLUÍDA e validada (verify_cipher_fixes 9/9; verify_p3a/p3b/p3c verdes)

Revisão de segurança (metodologia CIPHER: contratos quebrados, testes fracos,
fallure/edge, injeção/segurança, débito técnico) sobre P0–P3c. Abaixo o mapa de
achados e o estado após remediação.

## Resumo de risco

| ID | Severidade | Título | Estado |
|----|-----------|--------|--------|
| CIPHER-001 | 🔴 CRÍTICO | Authorization bypass via `user_role` do caller | ✅ RESOLVIDO (BLOCO 1) |
| CIPHER-002 | 🔴 CRÍTICO | `WindowsSelectorEventLoopPolicy` hardcoded (quebra no Linux) | ✅ RESOLVIDO (já protegido + `compat.py`) |
| CIPHER-017 | 🟡 MÉDIO | Sem git (zero histórico/rollback) | ✅ RESOLVIDO (BLOCO 1) |
| CIPHER-004 | 🟠 ALTO | `MCPClient` sem error handling | ✅ RESOLVIDO (BLOCO 2) |
| CIPHER-011 | 🟠 ALTO | Prompt injection via MCP externo | ✅ RESOLVIDO (BLOCO 2) |
| CIPHER-018 | 🟠 ALTO | Sem timeout em `tool.ainvoke` | ✅ RESOLVIDO (BLOCO 2) |
| CIPHER-010 | 🟡 MÉDIO | Audit via docker logs (frágil) | 🔵 DEFERIDO → P4 (schema `audit_logs` + policy escrita em DB) |
| CIPHER-005 | 🟡 MÉDIO | Stub `email_send` valida caminho errado | 🔵 DEFERIDO → P5 |
| CIPHER-013 | 🟡 MÉDIO | `.env` sem `.gitignore` | ✅ RESOLVIDO (BLOCO 1) |
| CIPHER-012 | 🔵 BAIXO | `approval_id` exposto no response | ✅ RESOLVIDO (BLOCO 3) |
| CIPHER-007 | 🔵 BAIXO | `http_list_tools` checa só `len > 0` | ✅ RESOLVIDO (BLOCO 3) |
| CIPHER-014 | 🔵 BAIXO | `host.docker.internal` só no Windows | ✅ RESOLVIDO (BLOCO 4) |

**Declaração de risco:** o sistema estava INSEGURO para P4 enquanto CIPHER-001
estivesse aberto (um único request com `user_role: "admin"` bypassava todo o
PolicyEngine). Com BLOCO 1 aplicado, o papel é resolvido **server-side** e o
bypass via payload está fechado — sistema seguro para iniciar P4.

## BLOCO 1 — críticos (pré-P4)

### CIPHER-001 — Authorization bypass (RESOLVIDO)
**Causa:** `src/jefrey/mcp/server.py:_make_wrapper` gerava `user_role: str = 'user'`
como parâmetro da ferramenta MCP. Qualquer cliente enviando `"user_role": "admin"`
no payload fazia `PolicyContext.user_role="admin"` → `policy.decide()` retornava
`ALLOW` (`admin bypass`), contornando HIGH/CRITICAL.

**Fix:**
- Removido `user_role` do schema de toda ferramenta (`_make_wrapper` não o gera mais;
  `_run_guarded` não o recebe mais).
- Papel resolvido **server-side** em `_resolve_role()`: `service_role` (config) é a
  fonte de verdade; um header `X-Jefrey-Role` só é aceito se estiver em
  `allowed_roles` (default `["user"]`). Sem isso, nenhum cliente se autodeclara admin.
- `MCPServerSettings` ganhou `service_role: str = "user"`, `allowed_roles:
  list[str] = ["user"]`, `tool_timeout: float = 30.0`.
- n8n `Build MCP Payload` atualizado para NÃO encaminhar `user_role` (senão toda
  chamada quebrava por argumento desconhecido).
- `verify_p3a.py` reescrito para DOIS servidores: USER (:8001, default) e ADMIN
  (:8002, `service_role=admin`) — o bypass admin agora é provado via **config**, não
  via payload. `verify_p3b.py` teve o teste de admin invertido para afirmar que o
  payload `user_role=admin` agora é **ignorado** (HIGH bloqueada).

**Critério de aceite:** `curl -H "X-Jefrey-Role: admin"` ignorado (não está em
`allowed_roles`); payload `{"user_role":"admin"}` ignorado (campo inexistente);
verify_p3a/p3b verdes. ✅

### CIPHER-002 — WindowsSelectorEventLoopPolicy (RESOLVIDO)
`scripts/verify_p2.py`, `verify_p3b.py`, `smoke_test.py` JÁ tinham o guard
`if sys.platform == "win32":` (o `findstr` inicial casou a linha interna, mas ela
estava protegida). Criado `src/jefrey/core/compat.py::configure_event_loop()` para
uso futuro em novos entrypoints. `verify_cipher_fixes` confirma a guarda nos 3.

### CIPHER-017 + CIPHER-013 — Git e .gitignore (RESOLVIDO)
`git init` + `git config user` + `.gitignore` cobrindo `.env`, `__pycache__`,
`logs/`, `data/`, volumes Docker, etc. Commit baseline `a6b1605`. `.env` NÃO é
versionado (`git check-ignore .env` confirma). Arquivos temporários de debug
(`scripts/_probe*`, `_inspect*`, `_tmp*`) removidos do baseline.

## BLOCO 2 — altos (antes de P4)

### CIPHER-004 — MCPClient error handling (RESOLVIDO)
`MCPClientError` ganhou `tool`/`original`; `connect()` e `call_tool()` envolvem
o transporte em `try/except` e não vazam stack traces internos. `call_tool` usa
`asyncio.wait_for` com `self._timeout`.

### CIPHER-018 — Timeout em tool.ainvoke (RESOLVIDO)
`MCPServerSettings.tool_timeout` (30s) aplicado via `asyncio.wait_for` em
`_run_guarded`; timeout retorna JSON de erro controlado (sem expor stack trace).

### CIPHER-011 — Prompt injection via MCP externo (RESOLVIDO)
`src/jefrey/core/content_guard.py::sanitize_tool_output()` bloqueia padrões de
injeção (ignore instructions, system prompt, `<\|...\|>`, `[INST]`, `### Human:`…).
`MCPClient.call_tool()` sanitiza o output antes de entregar ao chamador/LLM.

## BLOCO 3 — P4 (aplicado agora onde possível)

### CIPHER-012 — approval_id exposto (RESOLVIDO)
Responses de bloqueio usam `"reference": <approval_id[:8]>` em vez de expor o
`approval_id` completo. `verify_p3b.py` atualizado para checar `"reference="`.

### CIPHER-007 — http_list_tools fraco (RESOLVIDO)
`verify_p3c.py` agora exige `>=17` ferramentas, presença de `save_note` e
`email_send`, e metadados (nome+descrição) de cada ferramenta.

### CIPHER-010 — Audit via DB (DEFERIDO → P4)
Permanecer com leitura de logs do servidor (funciona) até o schema `audit_logs`
estar disponível; então `verify_p3a` consultará Postgres diretamente (sem dependência
de container rodando). Não bloqueia P4.

## BLOCO 4 — P8 (aplicado agora, no-op no Windows)

### CIPHER-014 — host.docker.internal no Linux (RESOLVIDO)
`docker-compose.yml` (mcp-server) ganhou `extra_hosts: - "host.docker.internal:host-gateway"`
— no-op no Windows Docker Desktop, resolve no Linux. Sem condicionais.

## Verificação pós-remediação

```
python scripts/verify_cipher_fixes.py   → 9/9 checks passaram
python scripts/verify_p3a.py            → ✅ (LOW executa, HIGH bloqueia, admin via config)
python scripts/verify_p3c.py            → 14 passou, 0 falhou (smoke 7/7 + verify_p3b rc=0)
python -m compileall -q src scripts     → OK
```

**Conclusão:** CIPHER-001/002/004/011/012/013/014/017/018/007 resolvidos e validados.
Sistema seguro para iniciar **P4** (Security, guardrails, HITL approvals).
CIPHER-010 fica para P4 (audit em DB); CIPHER-005 fica para P5 (stub email real).
