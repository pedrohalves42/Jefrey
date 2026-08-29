# 19 — CIPHER Re-Run pós-P4 (Security/Quality Scan)

**Status:** ✅ Verificações re-rodadas verdes (verify_cipher_fixes **9/9** sem regressão; verify_p4 **6/6 AXIOM** idempotente 3× + compileall OK). **NOVO:** scan do código P4 abriu **7 findings** — 1 crítico (HITL REST sem auth), 3 médios, 3 baixos.

Re-roda do CIPHER pedida após o commit `2f68e31` (P4). Metodologia: contratos quebrados, testes fracos, edge/failure, injeção/segurança, débito técnico.

## Verificações re-executadas

```
python scripts/verify_cipher_fixes.py   -> 9/9 checks passaram   (sem regressao P4)
python scripts/verify_p4.py              -> 6/6 AXIOM (3x idempotente) + compileall OK
python -m compileall -q src scripts      -> OK
```

=> Nenhuma regressão dos findings CIPHER-001/002/004/007/011/012/013/014/017/018.
=> CIPHER-010 (audit Postgres) e BUG-P3a-01 (risco explícito) permanecem FECHADOS e validados em P4.

## Resumo de risco — NOVOS findings (código P4)

| ID | Severidade | Título | Categoria | Estado |
|----|-----------|--------|-----------|--------|
| CIPHER-019 | 🔴 CRÍTICO | HITL REST (`/approvals/*`) sem authn/authz | Segurança/Injeção | 🟠 ABERTO (CONFIRMADO) |
| CIPHER-020 | 🟡 MÉDIO | `/approvals/pending` vaza `arguments_json` | Segurança (info disclosure) | 🟠 ABERTO (CONFIRMADO) |
| CIPHER-021 | 🟡 MÉDIO | `mode="off"` faz bypass de RBAC | Segurança (edge) | 🟠 ABERTO (CONFIRMADO) |
| CIPHER-022 | 🟡 MÉDIO | Trust do `actor_role` no agent loop não é server-side (latente P5) | Segurança | 🟠 ABERTO (HIPÓTESE) |
| CIPHER-023 | 🔵 BAIXO | `ToolExecutor._invoke` faz `await` de callable sync | Edge/Broken contract | ⚪ ABERTO |
| CIPHER-024 | 🔵 BAIXO | `uuid.UUID(id)` inválido -> 500 em `/decide` | Edge/Broken contract | ⚪ ABERTO |
| CIPHER-025 | 🔵 BAIXO | `AuditLogger` engole exceções -> perda silenciosa de trilho | Tech debt | ⚪ ABERTO |

## Detalhe dos findings

### CIPHER-019 — HITL REST sem autenticação (CRÍTICO, CONFIRMADO)
**Arquivo:** `src/jefrey/api/approvals.py` (`build_approvals_app`, `list_pending`, `decide`).
**Causa:** `GET /approvals/pending` e `POST /approvals/{id}/decide` não têm nenhum
guard de authn/authz — não há token, header, middleware nem checagem de
`allowed_roles`. Qualquer cliente que alcance a porta pode:
- `POST /approvals/{id}/decide` → **aprovar/rejeitar QUALQUER approval**. O HITL é o
  ÚNICO gate de execução de ferramentas HIGH/CRITICAL no agent loop; sem auth, um
  atacante (ou n8n comprometido) auto-aprova `email_send`/`calendar_create`.
- `GET /approvals/pending` → enumerar todas as pendências (vide CIPHER-020).

É o espelho de CIPHER-001, mas na **fronteira humana**: lá o papel foi resolvido
server-side (`_resolve_role`); aqui a *decisão* de aprovação é pública. Enquanto o
app `build_approvals_app()` **não está montado** (pending task P5), não é explorável —
mas torna-se 🔴 assim que a porta for exposta.
**Ação (P5, bloqueante):** autenticar o app (token compartilhado / header `X-Jefrey-Approver`
validado contra `allowed_roles`, ou bind `localhost` + proxy autenticado, ou mTLS). Não
expor a porta sem isso.

### CIPHER-020 — Listagem de pendências vaza argumentos (MÉDIO, CONFIRMADO)
**Arquivo:** `src/jefrey/api/approvals.py` (`get_pending` -> `_row_to_dict`).
**Causa:** `GET /approvals/pending` retorna `arguments_json` completo de cada approval
HIGH/CRITICAL pendente — corpos de e-mail, destinatários, detalhes de calendário,
`thread_id`. Mesmo autenticado, é over-exposure de PII.
**Ação:** na listagem, retornar só `id`, `tool_name`, `risk_level`, `status`,
`created_by`, `expires_at` (omitir `arguments_json`; quem decide pode buscar detalhe
por id com escopo restrito).

### CIPHER-021 — `mode="off"` bypassa RBAC (MÉDIO, CONFIRMADO)
**Arquivo:** `src/jefrey/core/policy.py::PolicyEngine.decide`.
**Causa:** o primeiro branch é
`if self._mode == "off": return PolicyResult(ALLOW, ...)` — ANTES da checagem RBAC
(AXIOM #1). Ou seja, desligar a "policy" desliga também o controle de acesso: um
`guest` passaria a poder chamar ferramentas MEDIUM/HIGH. Se `"off"` for usado como
kill-switch, deve ser documentado como bypass total emergencial; se for "sem gating de
risco mas mantém acesso", o RBAC tem de vir antes.
**Ação:** mover a checagem RBAC para antes do short-circuit de `off` (ou documentar
explicitamente que `off` == bypass total e nunca ser o default em produção).

### CIPHER-022 — `actor_role` no agent loop não é server-side (MÉDIO, HIPÓTESE/latente)
**Arquivo:** `src/jefrey/core/executor.py::ToolExecutor.__init__` (recebe `actor_role`);
`src/jefrey/core/agent.py::_execute_tools` (passa hardcoded `"user"`).
**Causa:** no gateway MCP o papel é resolvido server-side (`_resolve_role`, CIPHER-001
fechado). No caminho do agente/`ToolExecutor`, o papel vem do chamador. Hoje o agente
hardcode `"user"` server-side, então está OK; mas **em P5**, quando a API aceitar o
papel do request, reincide CIPHER-001 neste caminho se não houver resolução server-side
+ `allowed_roles`.
**Ação (P5):** resolver `actor_role` server-side também no caminho agente/API (mesmo
padrão `_resolve_role` do gateway).

### CIPHER-023 — `await` de callable síncrono em `_invoke` (BAIXO)
**Arquivo:** `src/jefrey/core/executor.py::_invoke`.
**Causa:** `if hasattr(tool, "ainvoke"): return await tool.ainvoke(args)` senão
`return await tool(**args)`. Se o `tool_resolver` devolver uma função síncrona,
`await tool(**args)` levanta `TypeError: object ... can't be used in 'await' expression`.
Hoje só recebe LangChain `BaseTool` (tem `ainvoke`), então não dispara — mas é frágil.
**Ação:** usar `asyncio.iscoroutinefunction` e chamar sem `await` se for sync.

### CIPHER-024 — UUID malformado -> 500 (BAIXO)
**Arquivo:** `src/jefrey/api/approvals.py::decide` (`uuid.UUID(approval_id)`);
`src/jefrey/core/hitl.py::get`/`wait_for_decision`.
**Causa:** `id` não-UUID levanta `ValueError` não tratado -> 500. Broken contract / edge.
**Ação:** validar UUID e retornar 400/404 com mensagem controlada.

### CIPHER-025 — Perda silenciosa de trilho de auditoria (BAIXO)
**Arquivo:** `src/jefrey/core/audit.py::AuditLogger.log`.
**Causa:** `except Exception: logger.warning(...)` engole TODAS as falhas (inclusive
schema/conn ausente). Resiliência é intencional (não quebrar a ferramenta), mas a
ausência do trilho de audit (CIPHER-010) é silenciosa — num incidente forense o log
pode estar vazio sem alerta.
**Ação:** além do warning, emitir métrica/contador de falha de audit; considerar
fallback para append-only local se o Postgres cair.

## Conclusão

- **Sem regressão:** todos os CIPHER anteriores permanecem FECHADOS; verify_cipher_fixes
  9/9 e verify_p4 6/6 verdes após P4.
- **P4 introduziu 1 crítico + 3 médios + 3 baixos.** O crítico (CIPHER-019) só é
  explorável APÓS montar `build_approvals_app()` na porta — o que é tarefa P5. Recomenda-se
  fechar CIPHER-019/020/022 **antes** de qualquer exposição de porta (P5), e tratar
  021/023/024/025 no mesmo pacote. Nenhum deles bloqueia o uso server-side atual (agent
  loop com humano no terminal), mas bloqueia a exposição em rede.
- **CIPHER-005** (`email_send`/`calendar_create` stubs) segue deferido para P5.
