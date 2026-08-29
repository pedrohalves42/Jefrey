# 18 — P4: Security, Guardrails & HITL (Implementação)

**Status:** ✅ P4 CONCLUÍDA e validada (verify_p4 6/6 AXIOM, idempotente 3x, compileall OK; verify_cipher_fixes 9/9 sem regressão; gateway MCP em modo autônomo reproduz P3b — user HIGH bloqueado, admin HIGH executa).

## Decisões de Arquitetura (confirmadas pelo usuário)

| # | Tópico | Escolha | Justificativa |
|---|--------|---------|---------------|
| 1 | RBAC | **Opção A** — 3 papéis fixos `admin`/`user`/`guest` | Jefrey é assistente pessoal, não multi-tenant. Overhead da Opção B não se paga. |
| 2 | HITL | **Opção A agora** (REST `GET /approvals/pending` + `POST /approvals/{id}/decide`) + **Opção B em P5** (webhook n8n) | REST é o que os testes validam deterministicamente; notificação real é fase de interface. |
| 3 | MCPClient | **Opção B** — registro explícito no `ToolRegistry` | CIPHER-011 (prompt injection) ainda é risco teórico vivo; descoberta automática amplia superfície antes de P7. |

## Entregáveis

| Arquivo | Descrição | Status |
|---------|-----------|--------|
| `src/jefrey/core/rbac.py` | `Role` (guest/user/admin) + `RBACEngine` + decorador `@require_role` | ✅ |
| `src/jefrey/core/registry.py` | `ToolRegistry` canônico (risco + `required_role` explícitos); `register_default_tools()` popula todas as ferramentas reais das skills (30 tools) | ✅ |
| `src/jefrey/core/policy.py` | risco **declarado** por ferramenta (sem heurística de nome — fecha BUG-P3a-01); RBAC **antes** do PolicyEngine; `UNKNOWN` fail-safe; admin bypass; HITL via `ApprovalManager` | ✅ |
| `src/jefrey/core/hitl.py` | `ApprovalManager`: `create` / `get_pending` / `decide` / `expire` / `wait_for_decision` (approval_ttl) | ✅ |
| `src/jefrey/core/audit.py` | `AuditLogger` → tabela Postgres `audit_logs` (fecha **CIPHER-010** — sai de docker logs) | ✅ |
| `src/jefrey/core/executor.py` | `ToolExecutor` — orquestra RBAC→Policy→HITL(polling)→execução (polling do agent loop, fatorado de `agent.py` p/ testabilidade) | ✅ |
| `src/jefrey/core/agent.py` | `_execute_tools` refatorado para delegar ao `ToolExecutor` (human-in-the-loop, `autonomous=False`) | ✅ |
| `src/jefrey/mcp/client.py` | `register_explicit()` (Opção B, Decisão 3) | ✅ |
| `src/jefrey/mcp/server.py` | `register_default_tools()` em `build_server()` (mantém risco/papel no gateway) | ✅ |
| `src/jefrey/api/approvals.py` | REST Starlette: `GET /approvals/pending`, `POST /approvals/{id}/decide` (Opção A, Decisão 2) | ✅ |
| `src/jefrey/core/models.py` | `Approval.expires_at` + `AuditLog` | ✅ |
| `src/jefrey/core/config.py` | `HITLSettings` (`approval_ttl=1800`, `poll_interval=2.0`) | ✅ |
| `src/jefrey/core/schema.py` | migration idempotente `ALTER TABLE approvals ADD COLUMN expires_at` | ✅ |
| `scripts/verify_p4.py` | cobertura dos 6 critérios AXIOM (idempotente 3x + compileall) | ✅ |

## Critério de Aceite P4 — 6/6 AXIOM (verify_p4.py)

| # | Critério | Resultado |
|---|----------|----------|
| 1 | Guest tenta tool MEDIUM → bloqueado por RBAC **antes** do PolicyEngine | ✅ `deny_rbac` (papel guest insuficiente para `create_workflow`) |
| 2 | User tenta tool HIGH → approval criado → humano aprova via REST → tool executa | ✅ executou após `decide(approved)` |
| 3 | User tenta tool HIGH → humano rejeita via REST → não executa + audit registra rejeição | ✅ não executou; `audit_logs` com `approval_decision=rejected` |
| 4 | Admin executa tool HIGH direto → sem approval → audit `role=admin` | ✅ executou; `audit_logs` com `actor_role=admin, decision=allow` |
| 5 | Risco declarado explicitamente; ferramenta nova sem risco → `UNKNOWN` bloqueada | ✅ `ferramenta não registrada no ToolRegistry (risco desconhecido)` |
| 6 | verify_p4 idempotente 3x + compileall + regressão P1/P2/P3a/P3b/P3c/cipher | ✅ 3x verde + compileall; CIPHER 9/9; gateway em modo autônomo = P3b |

## Modelo de decisão (policy.decide)

```
1. RBAC(actor, required_role)         -> DENY  (AXIOM #1: antes do risco)
2. risco == UNKNOWN (não registrada)  -> DENY  (fail-safe, AXIOM #5)
3. actor == admin                     -> ALLOW (AXIOM #4: bypass HITL)
4. risco HIGH/CRITICAL                -> HITL (cria approval; espera decisão se ctx.autonomous=False)
5. risco LOW/MEDIUM                   -> ALLOW (auto-aprovado)
```
No gateway MCP (`ctx.autonomous=True`), HIGH/CRITICAL retorna **DENY** (bloqueado, approval registrado p/ análise) — mantém P3b verde. No agent loop (`autonomous=False`), retorna **HITL** e o `ToolExecutor` faz `wait_for_decision`.

## RISCO ATIVO (fechado)

O polling de approval no agent loop tem teto via `approval_ttl` (padrão **30 min**, `JEFREY_HITL__APPROVAL_TTL`). `ApprovalManager.expire_due()` marca pendências vencidas como `expired`; `wait_for_decision` retorna `expired` ao esgotar o prazo e o `ToolExecutor` **nega automaticamente** a ferramenta — o agente não trava para sempre.

## Como validar

```bash
# 1) sobe Postgres/Redis (docker-compose) — necessário para approvals/audit_logs
docker compose up -d db redis

# 2) P4 — 6/6 AXIOM, idempotente 3x, compileall
python scripts/verify_p4.py

# 3) regressão CIPHER (estático, sem serviços)
python scripts/verify_cipher_fixes.py

# 4) regressões P3 (gateway) — requer servidor MCP rodando (P3a/P3b/P3c)
python scripts/verify_p3b.py && python scripts/verify_p3c.py
```

## Deferidos (não são P4)

- **CIPHER-005** — `email_send`/`calendar_create` ainda são stubs (envio/OAuth real) → **P5**.
- **Decisão 2 — Opção B** — webhook n8n para notificar o humano → **P5** (REST pronto em P4).
- **Decisão 3 — Opção A** — descoberta automática de tools MCP → rejeitada em favor de registro explícito (CIPHER-011).

## Notas de implementação

- `ToolExecutor` vive em módulo leve (`executor.py`, sem LangGraph) para ser testável de forma determinística; `agent._execute_tools` delega a ele. É a implementação do "polling de approval" listado no escopo, fatorada para isolamento de dependências (refino análogo ao "ToolRegistry home" acordado).
- `RiskLevel.UNKNOWN` adicionado; `risk_of()` consulta o `ToolRegistry` e nunca mais usa heurística de nome (BUG-P3a-01 fechado definitivamente).
- `ApprovalStore` (antigo, em `policy.py`) substituído por `ApprovalManager` (com `expires_at`); nenhuma referência órfã restante.
