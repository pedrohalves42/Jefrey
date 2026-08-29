# JEFREY — Fase P2: OpenAI Agents SDK & Responses API + Checkpointer Postgres

**Data:** 2026-08-28
**Objetivo (roadmap):** "OpenAI Agents SDK & Responses API (substituir LangGraph/MemorySaver por Postgres)".

---

## 1. Decisão de Arquitetura

O runtime `langgraph` **permanece o default** (funciona com Ollama local, usado no `.env` atual).
A Fase P2 entrega:

1. **Persistência Postgres no lugar do `MemorySaver` em memória** — cumprido para o runtime langgraph via `AsyncPostgresSaver` (`langgraph-checkpoint-postgres`). O estado do grafo agora sobrevive a reinícios.
2. **Novo runtime `openai`** baseado em OpenAI Agents SDK & Responses API (`agents.Agent` + `agents.Runner`), selecionável por `JEFREY_AGENT__PROVIDER=openai`, com sessões persistidas em Postgres (`PostgresSessionStore`).

> Ollama **não** implementa a *Responses API* da OpenAI, por isso o runtime `openai` exige um endpoint compatível (ex.: `api.openai.com`). Por isso o default segue `langgraph`.

---

## 2. Arquivos Criados / Editados

| Arquivo | Tipo | Conteúdo |
|---|---|---|
| `src/jefrey/core/checkpointer.py` | NOVO | `get_postgres_checkpointer()` / `close_postgres_checkpointer()` — `AsyncPostgresSaver` singleton, `setup()` idempotente, DSN psycopg puro. |
| `src/jefrey/core/openai_agent.py` | NOVO | `OpenAIAgent` (Agents SDK), `PostgresSessionStore` (`agent_sessions`), `_convert_tool()` (LangChain→`function_tool`), ferramenta `memory_search`. |
| `src/jefrey/core/agent.py` | EDITADO | Facade por `provider`; remoção de `MemorySaver`; compilação lazy com checkpointer Postgres; delegação run/stream/health_check ao backend `openai`. |
| `src/jefrey/core/config.py` | EDITADO | `AgentSettings` (`provider`, `openai_api_key`, `openai_base_url`, `openai_model`, `system_prompt`) + campo `agent` em `AppSettings`. |
| `scripts/verify_p2.py` | NOVO | Verificação e2e da Fase 2. |
| `requirements.txt` | EDITADO | `+ openai-agents>=0.1,<2`, `+ langgraph-checkpoint-postgres>=2,<4`. |
| `scripts/smoke_test.py` | EDITADO | `main()` usa `WindowsSelectorEventLoopPolicy` no Windows (requisito do psycopg assíncrono). |
| `JEFREY-AUDIT/05_MASTER_ROADMAP.md` | EDITADO | Tabela de status P0–P8 + nota de arquitetura P2. |

---

## 3. Dependências Instaladas

- `openai-agents==0.22.0` (puxou `openai==3.6.0`, `mcp==2.1.1`, etc.).
- `langgraph-checkpoint-postgres==3.1.2` (puxou `langgraph-checkpoint==4.2.0`, `psycopg-pool==3.3.1`).

> **Nota de compatibilidade:** o upgrade de `openai` para 3.6.0 é compatível com `langchain-openai` (smoke 7/7 confirmado). O smoke e o `verify_p1` continuam verdes após a instalação.

---

## 4. Detalhes de Implementação

### 4.1 Checkpointer Postgres (`checkpointer.py`)
- `AsyncPostgresSaver.from_conn_string(dsn)` é um *async context manager*; o saver entrado é cacheado (singleton) e `await saver.setup()` cria as tabelas `checkpoints`/`checkpoint_writes`/`checkpoint_blobs` (idempotente).
- DSN convertido de `postgresql+psycopg://` (SQLAlchemy) para `postgresql://` (psycopg puro).
- **Windows:** psycopg v3 assíncrono exige `SelectorEventLoop` (o `ProactorEventLoop` padrão falha com `InterfaceError`). Resolvido nos pontos de entrada (`smoke_test.main`, `verify_p2.main`).

### 4.2 Runtime `openai` (`openai_agent.py`)
- `OpenAIAgent(tools, model)`: converte ferramentas LangChain via `_convert_tool` (reconstrói a assinatura a partir de `args_schema.model_fields` para um schema JSON fiel) e anexa `memory_search` (busca na memória de longo prazo Postgres+pgvector).
- `run(user_input, thread_id)`: carrega histórico de `PostgresSessionStore`, chama `Runner.run(agent, input=items)`, persiste `result.to_input_list()` e salva a conversa na memória de longo prazo.
- `stream(...)`: usa `Runner.run_streamed` e emite deltas de texto.
- `health_check()`: valida o `PostgresSessionStore` sem chamar o modelo (evita custo).
- `_ensure_agent_config()`: aplica `set_default_openai_key` e `OPENAI_BASE_URL` (agents 0.22 não expõe `set_default_openai_base_url`) e desliga tracing.

### 4.3 Facade (`agent.py`)
- `JefreyAgent(tools)` lê `JEFREY_AGENT__PROVIDER`: `openai` → `OpenAIAgent` (delega run/stream/health_check); `langgraph` (default) → grafo LangGraph compilado **sob demanda** com o checkpointer Postgres via `_compile()`.

---

## 5. Verificação (tudo verde)

| Teste | Comando | Resultado |
|---|---|---|
| Sintaxe (`src/`) | `python -m compileall -q src` | ✅ exit 0 |
| Fase 2 e2e | `python scripts/verify_p2.py` | ✅ PASS |
| Smoke (regressão) | `python scripts/smoke_test.py` | ✅ 7/7 (Agente Básico: `healthy`, `checkpoint=ok`) |
| Fase 1 (regressão) | `python scripts/verify_p1.py` | ✅ PASS |
| Import-time core | import de agent/checkpointer/openai_agent | ✅ OK |

`verify_p2.py` prova especificamente:
- **Persistência LangGraph+Postgres:** 2 turnos no mesmo `thread_id` acumulam 4 mensagens (estado sobrevive entre invocações — o antigo `MemorySaver` perdia tudo ao reiniciar).
- **PostgresSessionStore:** round-trip em `agent_sessions`.
- **OpenAIAgent:** constrói, `health_check` ok, ferramenta `memory_search` presente.
- **JefreyAgent (langgraph+Postgres):** `status=healthy`, `checkpoint=ok`.
- Run real na OpenAI: pulado por padrão (gate `JEFREY_ALLOW_LIVE_OPENAI=1` + `OPENAI_API_KEY`).

---

## 6. Como Habilitar o runtime OpenAI

```bash
# .env
JEFREY_AGENT__PROVIDER=openai
JEFREY_AGENT__OPENAI_API_KEY=sk-...        # ou use a env OPENAI_API_KEY já existente
JEFREY_AGENT__OPENAI_BASE_URL=            # opcional (ex.: proxy compatível com Responses API)
JEFREY_AGENT__OPENAI_MODEL=gpt-4o-mini
```

```bash
# Execução ponta a ponta real (custa tokens):
set JEFREY_ALLOW_LIVE_OPENAI=1
python scripts/verify_p2.py
```

---

## 7. Itens Pendentes / Observações

- Run real na OpenAI não foi executado nesta validação (sem flag + custo). A lógica está implementada e o caminho é coberto por import/health_check/round-trip.
- `agents` 0.22 não expõe `set_default_openai_base_url`; base URL customizada via `OPENAI_BASE_URL` env (documentado).
- `WindowsSelectorEventLoopPolicy` está deprecado no Python 3.16 (apenas warning); em Linux o default funciona. Para produção em Windows, manter o policy ou usar uvicorn com loop compatível.
- A sessão do runtime `openai` persiste apenas a conversa (`to_input_list()`); contexto de memória de longo prazo é trazido sob demanda pela ferramenta `memory_search` (design agentic).

---

## 8. Próximo Passo

**Fase P3:** MCP gateway + n8n bridge (aproveitar `mcp==2.1.1` já instalado pelo `openai-agents`).

---

## 9. Revalidação AXIOM (2026-08-28) — BUG-P2-01

Durante a revalidação rigorosa (regra AXIOM #2: ler código antes de afirmar), o
`verify_p2.py` **não passou em re-execução** — a alegação de "PASS" no resumo era um
*one-shot pass* e o teste não era idempotente.

- **Sintoma:** `assert len(r2["messages"]) == 4` falhou com 8 (1ª re-exec), depois 12.
- **Causa raiz:** `_test_langgraph_postgres_persistence` usa `tid = "persist-test"` fixo e
  nunca limpava o thread. Como o checkpointer P2 é **durável** (Postgres), o estado das
  execuções anteriores acumulava (4 + 4 + 4...). Ao tentar corrigir, a limpeza foi chamada
  como `await cp.adelete_thread([tid])` — **errado**: a API `AsyncPostgresSaver.adelete_thread`
  recebe um ÚNICO `thread_id: str`, não uma lista. A lista não casava no
  `WHERE thread_id = %s` e nada era deletado (contagem ficava em 18 linhas órfãs).
- **Correção:** `await cp.adelete_thread(tid)` (string) no início do teste → garante thread
  fresco → exatamente 4 mensagens em 2 turnos. Teste agora idempotente.
- **Severidade:** MÉDIO (confiabilidade de teste; não afeta runtime de produção).
- **Arquivo:** `scripts/verify_p2.py` (linha ~66, em `_test_langgraph_postgres_persistence`).
- **Validação pós-fix:** `verify_p2.py` PASS em 3 execuções consecutivas; `smoke_test.py`
  7/7; `verify_p1.py` PASS. Tudo verde.

### Estado de SEG/OBS (atualizado 2026-08-28 — RESOLVIDO em §10)
- `OpenAIAgent` e `JefreyAgent` (LangGraph) agora aplicam `PolicyEngine` (RBAC/HITL) em toda
  chamada de ferramenta, com auditoria estruturada → ver §10.
- `logging.py` (JSON) está conectado aos dois runtimes; `health_check` reporta `policy`.
- `WindowsSelectorEventLoopPolicy` deprecado no Python 3.16 (warning apenas; obrigatório no
  Windows com psycopg v3 async) — latente, sem ação em P2.

---

## 10. Fechamento de critérios AXIOM (100%) — 2026-08-28

P2 elevada de 80% → 100%. Foram fechados os critérios de **SEGURANÇA** e **OBSERVABILIDADE**.

### 10.1 Segurança — Policy Engine (RBAC/HITL)
- Novo `src/jefrey/core/policy.py`:
  - `PolicyEngine.decide(tool, args, ctx)` → `ALLOW` | `HITL` | `DENY` por `RiskLevel`
    (LOW/MEDIUM auto-aprovados; HIGH/CRITICAL exigem HITL).
  - Classificação por convenção de nome (`notes_*=LOW`, `web_search`/`memory_search`=LOW,
    `automation_*`=MEDIUM, `email_*`/`calendar_*`=HIGH; desconhecido=HIGH fail-safe).
  - `RunContext/PolicyContext` com `user_role` (admin bypass) e `autonomous`.
  - `ApprovalStore` persiste pedidos HITL na tabela `approvals` (Postgres) — cola o HITL (P4/P5).
  - `audit()` emite log estruturado de todo call de ferramenta.
- **Runtime OpenAI**: `_convert_tool` + `_guarded_call` envolvem cada ferramenta; `ctx: RunContextWrapper`
  carrega `thread_id` → policy é aplicada antes da execução (`memory_search` também protegido).
- **Runtime LangGraph** (`agent.py`): `_execute_tools` aplica `policy.decide` antes de `tool.ainvoke`;
  DENY/HITL retornam mensagem bloqueada e emitem `TOOL_RESULT{blocked:true}`.
- Config: `JEFREY_POLICY__MODE` (`enforce`|`audit`|`off`) e `JEFREY_POLICY__AUTONOMOUS`.

### 10.2 Observabilidade
- `logging.py` (JSON) conectado em `openai_agent.py` e `agent.py` (ativa no load do runtime).
- `OpenAIAgent.run` loga início/fim; `PolicyEngine.audit` loga cada `tool_call`
  (tool/risk/decision/thread/approval).
- `health_check` (ambos runtimes) reporta `policy` + `policy_mode`.

### 10.3 Critério de aceite (mapa AXIOM)
| Critério | Estado | Evidência |
|----------|--------|-----------|
| IMPLEMENTAÇÃO | ✅ | checkpointer Postgres + OpenAIAgent + PolicyEngine + ApprovalStore |
| TESTE | ✅ | `verify_p2.py` PASS (persistência + session + PolicyEngine/HITL + health) |
| SEGURANÇA | ✅ | PolicyEngine RBAC/HITL nos 2 runtimes; approvals persistidos; fail-safe HIGH/CRITICAL |
| OBSERVABILIDADE | ✅ | logs JSON + audit de tool calls + health_check com policy |
| DOCUMENTAÇÃO | ✅ | este documento (§1–§10) + `05_MASTER_ROADMAP.md` |
| CRITÉRIO DE ACEITE | ✅ | `verify_p2` + `smoke` 7/7 + `verify_p1` verdes e re-executáveis |

**Latente (fora de P2, por design):** UI de HITL (P4/P5); RBAC por papel completo (P4);
métricas OTel/Prometheus (P6) — contadores atuais via logging; run real OpenAI gated por
`JEFREY_ALLOW_LIVE_OPENAI=1`.

**P2 = 100% concluída.**
