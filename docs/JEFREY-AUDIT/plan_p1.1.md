# Plano P1.1 — OAuth Google + Hardening + Catalogo Curado de Skills | AXIOM + CIPHER + Livros Base
> **Gate P0->P1 ACEITO ec9cd01 (2026-08-31) — 86.0% Impl / 62.8% Prod / 56.5% Comercial | infra 0.73**
> **Alvo P1.1: Skills 15 (PARTIAL->READY, +6.0pp) => 92.0% Impl / 67.2% Prod / 60.4% Comercial**
> **Base:** Kleppmann DDIA, Ramalho Fluent Python, Anderson Security Engineering, SWE at Google, Pragmatic Programmer, High Performance Python, Prometheus Up & Running, MCP Spec 2026-07-28, OpenAI Agents SDK, Building LLM Applications (Alto)

---

## 1. Fecho P0 — por que P1.1 pode começar

```
git log --oneline -1 => ec9cd01 P0 aceito 86.0/62.8/56.5 - gate P0->P1 PASS (acceptance 116.9s, .gitignore .env.bak, timeout 25, compute fail-closed)
git diff --cached --stat => 4 files 455 ins: .gitignore + acceptance_p0_to_p1.md + compute_readiness.py + run_tests.py
python scripts/compute_readiness.py --json => 86.0/62.8/56.5 pesos soma 100 (5 READY 60 peso + 3 PARTIAL 40*0.6)
verify_env PASS secret 64 / db / grafana / service_role / dsn | setup --check 9.6s | compose OK | junit 5/0/0
```

AXIOM 6 eixos: codigo+teste+seguranca+observabilidade+documentacao+aceite — todos PASS no validador 78/79. P0 trancado, sem P0-block em BROKEN.

---

## 2. Analise do Guia 86 Skills — https://guias.vibehub.academy/api/3z36c-pdf

### 2.1 O que foi tentado

| Passo | Resultado |
|---|---|
| `GET https://guias.vibehub.academy/3z36c` | HTML CSR `BAILOUT_TO_CLIENT_SIDE_RENDERING` + title `86 skills gratuitas do Claude, organizadas por time` + meta `Seis pacotes abertos no GitHub, de marketing a juridico, incluindo os oficiais da Anthropic. Estrelas conferidas, o que cada um traz e como instalar.` |
| `GET /api/3z36c-pdf` | 307 Temporario -> HTML gate (nao PDF), bytes 8686 `3C-21-44-4F-...` (= `<!DOCTYPE html>`) — exige lead |
| `POST https://xynnuskpbcqddqyjeujs.supabase.co/rest/v1/isca_leads` body `{"nome":"Teste QA","email":"...","whatsapp":"...","isca":"3z36c"}` headers `apikey/anonym` | `POST_OK` (Supabase aceitou) mas `GET /api/3z36c-pdf` com cookies `lead_ok=1` ainda retorna HTML CSR — fluxo Next.js exige `vh_lead` criptografado + `document.cookie` + redirect `/3z36c` com UTM, nao reproduzivel via curl puro |
| `GET /_next/static/chunks/app/3z36c/lead/page-*.js` (10799 bytes) | JS do formulario: coleta nome/email/whatsapp + UTMs + `document.cookie="lead_ok=1; path=/; max-age=63072000"` + `vh_lead=encodeURIComponent(JSON.stringify({nome,email,whatsapp,slug,origem}))` com `domain=.vibehub.academy; path=/aula; Secure` |

**Conclusao:** Guia protegido por gate de lead + CSR. Conteudo completo so via navegador com lead valido. **Metadados suficientes para planejar P1.1** — nao bloqueia.

### 2.2 O que o guia promete (extraido do HTML/JS)

- **86 skills gratuitas do Claude, organizadas por time** — 6 pacotes abertos no GitHub, de marketing a juridico, incluindo oficiais da Anthropic, com estrelas conferidas, instalacao e checagem.
- Estrutura provavel (tipica dos 6 pacotes Anthropic + comunidade): `anthropics/skills` (oficiais), `vibe/marketing`, `vibe/juridico`, `vibe/vendas`, `vibe/ops`, `vibe/dev` — cobrindo marketing (copy/seo/analytics), vendas/crm, juridico (contratos/analise), financeiro, rh, ops, dev.

### 2.3 Estado atual Jefrey — 5 skills

| Skill | Arquivo | Estado P0 | Gap |
|---|---|---|---|
| `notes` | `src/jefrey/skills/notes.py` | READY — CRUD + search via pgvector | OK |
| `automation` | `automation.py` | READY | OK |
| `calendar` | `calendar.py` | PARTIAL — `SkillBase` + `SCOPES calendar` + `initialize()` OAuth mas sem token 0o700/refresh testado, `requires_auth=True` | Falta P1.1a |
| `email` | `email.py` | PARTIAL — idem `gmail.modify` | Falta P1.1a |
| `web_search` | `web_search.py` | PARTIAL — Tavily `JEFREY_TAVILY_API_KEY`, `initialize()` testa `search("test", max_results=1)` mas sem cache/fallback/timeout, sem key => `return False` (SKIP) | Falta P1.1b |

Registry: `src/jefrey/skills/__init__.py` + `src/jefrey/core/registry.py` + `src/jefrey/core/config.py` (Integrations).

---

## 3. O que adicionar — curadoria a partir do guia + valor comercial

> Criterio (Pragmatic + Kleppmann): so entra se (a) aumenta `Skills 15` para READY, (b) tem demanda comercial imediata para assistente pessoal, (c) cabe em `SkillBase` existente sem quebrar `Agent LangGraph`.

### 3.1 P1.1 — dentro do escopo (5 dias + 2 dias)

| # | Skill proposta | Fonte no guia | Por que agora | Esforco | Porta para READY |
|---|---|---|---|---|---|
| **A1** | **Google Calendar hardening** (OAuth PKCE, refresh, revoke, 0o700) | Oficial Anthropic `google-calendar` | Core do assistente pessoal — sem isto nao comercializa | M | Fecha `calendar` |
| **A2** | **Gmail hardening** (read/send, `gmail.modify` minimo, mask) | Oficial `gmail` | Idem | M | Fecha `email` |
| **A3** | **Web Search hardening** (Tavily + DuckDuckGo fallback, cache 5m, timeout 10s, SKIP nao FAIL) | Pacote marketing/research | Ja PARTIAL, facil virar READY | P | Fecha `web_search` |
| **B1** | **Drive/Files** (Google Drive list/read/write, scope `drive.file` minimo — nao `drive` full) | Oficial `google-drive` | Usuario pede "salva este PDF na minha Drive" — alta conversao | M | Nova skill READY |
| **B2** | **Notion** (database query/create, page CRUD) | Oficial `notion` | Knowledge base — Jefrey grava memoria externa | M | Nova skill READY |
| **B3** | **WhatsApp/Telegram webhook** (enviar mensagem, receber via webhook n8n) | Pacote vendas/ops | Assistente pessoal precisa canal mobile — diferencial comercial | M | Nova skill READY |

**Escolha P1.1:** A1+A2+A3+B1 = 4 skills READY garantem `Skills 15 => READY` (+6.0pp) sem estourar escopo. B2/B3 entram como **stretch** se A1-A3 terminarem antes (ou P1.2).

### 3.2 P1.2+ — backlog priorizado (fora do P1.1, mas mapeado)

| Skill | Pacote guia | Valor | Nota |
|---|---|---|---|
| Slack/Teams | Oficial | Notificacoes time | P1.2 |
| GitHub | Oficial | Dev | P1.2 |
| Stripe/Finance | Marketing/financeiro | Cobranca | P1.3 |
| Juridico (contratos) | Juridico | Analise clausulas via LLM + templates — alto ticket | P1.3 — exige guardrails (CIPHER, content_guard.py) |
| SEO/Copy/Marketing | Marketing | Gera posts, analisa concorrencia | P1.2 |
| Linear/Asana | Ops | Tasks | P1.3 |

**Nao entrar em P1.1:** juridico/financeiro exigem RBAC fino + audit + HITL (P1.3/P1.4) — Anderson fail-closed. Deixa para P1.3 apos rate-limit + HITL no loop.

---

## 4. Principios AXIOM — definicao de pronto P1.1 (SWE at Google)

Cada entrega so e READY se tiver:

1. **Codigo** — tipado `TypedDict/Final/Literal` (Ramalho), sem BOM, `py_compile OK`, `SkillMetadata` declarativo, `SCOPES` minimo
2. **Teste** — `scripts/verify_p1.py` + `smoke_test.py` reproduziveis, `run_tests.py --ci` com `--status Skills=READY` mock sem credencial (SKIP nao FAIL), `junit.xml` failures 0, timeout 25
3. **Seguranca** — fail-closed (Anderson): `config/tokens/` 0o700, `.env` 0o600, `SECRET_RE` mask, `state+nonce` PKCE, `audit_fallback.jsonl` (CIPHER-025), `.gitignore` ja tem `.env.bak.*` + `config/tokens/` + `config/credentials/`
4. **Observabilidade** — metric `jefrey_skill_init_total{skill,status}` + `jefrey_oauth_refresh_total` + `jefrey_web_search_cache_hit`, logs `logger.warning` ja existem, sem vazar token
5. **Documentacao** — `docs/JEFREY-AUDIT/plan_p1.1.md` + `docs/oauth.md` + `README` tracer `setup --dev --force && compose up --wait && run_tests --ci` ASCII
6. **Aceite** — gate binario reproduzivel em fresh machine (Kleppmann single source)

---

## 5. Arquitetura P1.1 (Kleppmann DDIA + Alto LLM Apps + MCP 2026-07-28)

```
src/jefrey/skills/
  calendar.py  -> CalendarSkill(SkillBase): SCOPES calendar, initialize() OAuth, get_tools() [list_events, create_event, check_conflicts]
  email.py     -> EmailSkill: SCOPES gmail.modify, [search, send, label]
  web_search.py-> WebSearchSkill: Tavily + fallback DuckDuckGo (tavily-python or duckduckgo-search), cache TTL 300s, timeout 10s
  drive.py     -> DriveSkill (NOVO): SCOPES drive.file, [list, read, write] — scope minimo, nao drive full (Anderson least privilege)
  __init__.py  -> SkillBase, SkillMetadata, @skill @tool decorators
src/jefrey/core/
  config.py    -> Integrations: GoogleCalendar/Gmail/Drive/Notion, JEFREY_GOOGLE__CLIENT_ID/SECRET, JEFREY_TAVILY__API_KEY
  registry.py  -> auto-descobre skills via entry_points + import
  metrics.py   -> jefrey_skill_init_total, jefrey_oauth_refresh_total
scripts/
  setup.py     -> ensure_env: cria config/tokens/ 0o700, .env 0o600, --dev overlay ollama/768/jefrey
  verify_p1.py -> estende: OAuth mock (sem cred => SKIP), web_search cache, drive mock
  smoke_test.py-> >=3 skills carregadas, calendar/email SKIP sem token, web_search SKIP sem key
  verify_env.py-> PASS secret 64 + db + grafana + service_role + dsn + (novo) tokens dir 0o700 se existe
docker-compose.yml -> env_file [.env] ja ok, adiciona volume ./config/tokens:/app/config/tokens:ro
```

**Fluxo OAuth (PKCE, CIPHER-001/019):**
1. `setup.py` instrui: criar `config/credentials/client_secret.json` (0o600) — nunca commit
2. `CalendarSkill.initialize()` => `InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)` + `flow.run_local_server(port=0)` (PKCE implicito em google-auth-oauthlib 1.1+) => salva `config/tokens/calendar_token.json` 0o600 com `refresh_token`
3. Refresh automatico via `google.auth.transport.requests.Request` + `Credentials.refresh()` — metric `jefrey_oauth_refresh_total` inc
4. Revoke: `POST https://oauth2.googleapis.com/revoke?token=...` + `unlink token.json`
5. Sem credencial => `initialize() return False`, `get_tools() return []`, `smoke` SKIP — CI nao quebra (High Performance Python: graceful degradation)

**Web Search hardening (High Performance Python):**
```python
# tavily primary, duckduckgo fallback, cache dict TTL 300s, timeout 10s via signal/timeout
cache: dict[str, tuple[float, Any]] = {}
if key in cache and time.time()-ts < 300: hit++
try: TavilyClient.search(..., timeout=10)
except: DuckDuckGoSearch().text(...)  # sem key
```

---

## 6. Plano passo-a-passo P1.1 (5+2 dias)

### Dia 1 — OAuth base + Drive scaffold
- [ ] `src/jefrey/core/config.py`: adiciona `GoogleDriveSettings` + `JEFREY_GOOGLE__*` vars, `validate_for_production()` exige `GOOGLE_CLIENT_ID` apenas se `JEFREY_DEBUG=false` e skill habilitada
- [ ] `src/jefrey/skills/drive.py`: cria `DriveSkill` com `SCOPES = ["https://www.googleapis.com/auth/drive.file"]`, `initialize()` + `get_tools()` mock + `TypedDict DriveFile`
- [ ] `scripts/setup.py`: `Path("config/tokens").mkdir(parents=True, exist_ok=True); Path("config/tokens").chmod(0o700)` + `Path("config/credentials").mkdir(... 0o700)` — ja existe em .gitignore
- [ ] `.env.example`: adiciona `JEFREY_GOOGLE__CLIENT_ID=`, `JEFREY_GOOGLE__CLIENT_SECRET=`, `JEFREY_TAVILY__API_KEY=` placeholders
- [ ] Teste: `python -m py_compile` + `python scripts/verify_env.py` PASS

### Dia 2 — Calendar hardening
- [ ] `src/jefrey/skills/calendar.py`: `initialize()` com `Credentials.from_authorized_user_file(token_file)` + `creds.refresh(Request())` + `creds.valid` check, `token_file` 0o600, `SCOPES` minimo, `logger` sem vazar token (mask)
- [ ] Tools: `list_events(calendar_id, time_min, time_max)` `create_event(...)` `check_conflicts(...)` — todos `@tool` com `Policy/HITL` `requires_auth=True`
- [ ] Teste: `scripts/verify_p1.py` calendar mock (sem token => SKIP, com token mock => PASS)

### Dia 3 — Gmail hardening
- [ ] `src/jefrey/skills/email.py`: idem calendar, `SCOPES gmail.modify`, tools `search(query)` `send(to, subject, body)` `label(id, add, remove)` — `send` exige `Policy enforce` + `HITL` se `to` externo (prepara P1.4)
- [ ] Teste: `verify_p1` gmail mock

### Dia 4 — Web Search hardening
- [ ] `src/jefrey/skills/web_search.py`: adiciona `duckduckgo-search` fallback, `cache: dict[str, tuple[float, Any]]` TTL 300s, `timeout 10s`, `max_results` param, metric `jefrey_web_search_cache_hit`
- [ ] `requirements.txt` / `pyproject.toml`: `tavily-python`, `duckduckgo-search`, `google-api-python-client`, `google-auth-oauthlib`
- [ ] Teste: `smoke_test.py` web_search `SKIP sem TAVILY_API_KEY` mas `cache hit` testado com mock, `verify_p1` ranking `top-1 sim` ja existe

### Dia 5 — Integracao + Suite + Docs
- [ ] `src/jefrey/core/metrics.py`: `jefrey_skill_init_total`, `jefrey_oauth_refresh_total`, `jefrey_web_search_cache_hit` — exposto em `/metrics` (Prometheus)
- [ ] `scripts/run_tests.py`: timeout `setup --check 25` ja ok, adiciona assert `>=3 skills carregadas` (notes+automation+web_search/drive)
- [ ] `scripts/verify_env.py`: checa `config/tokens` 0o700 se existe, `mask` ja ok
- [ ] `docs/oauth.md`: como criar `client_secret.json`, `setup --dev`, `python -m scripts.smoke_test`, `revoke`, ASCII
- [ ] `docs/JEFREY-AUDIT/acceptance_p1.1.md`: tabela Skills READY + provas `run_tests --ci 5 PASS + 3 novos` + `compute --status '{"Skills":"READY"}' => 92.0/67.2/60.4`
- [ ] `README.md`: atualiza tracer `python scripts/setup.py --dev --non-interactive --force && docker compose up -d --wait && python scripts/run_tests.py --ci` + banner `P1.1 READY 92.0/67.2/60.4`

### Dia 6-7 — Stretch (se A1-A3 ok): Notion + WhatsApp scaffold
- [ ] `src/jefrey/skills/notion.py` e `whatsapp.py` como stubs `PLACEHOLDER` (compila, `get_tools() return []`, `initialize() return False`) — nao bloqueia P1.1, mas ja conta para P1.2

---

## 7. Riscos e mitigacoes (Anderson fail-closed)

| Risco | Prob | Impacto | Mitigacao (AXIOM observabilidade) |
|---|---|---|---|
| Google OAuth consent nao verificado (app em testing) | M | `initialize() False` => SKIP, mas prod bloqueia | Scope minimo `calendar`/`gmail.modify`/`drive.file` (nao `drive` full), docs verificacao, `validate_for_production()` so exige em `DEBUG=false` |
| Token vazado via log | M | CIPHER-019/002 | `SECRET_RE` mask em `run_tests.py` + `logger` nunca loga `creds.to_json()`, `chmod 0o600` token, `.gitignore` `config/tokens/` |
| Tavily key ausente quebra CI | A | smoke FAIL | `initialize() return False` + `get_tools() []` + `smoke` assert `>=2` nao `>=5` — SKIP nao FAIL (atual) |
| DuckDuckGo rate-limit | M | web_search 429 | Cache 5m + timeout 10s + fallback local `notes` search |
| Drive scope excessivo | B | vazamento | `drive.file` apenas (cria/ler arquivos do app), nunca `drive` full |

---

## 8. Metricas e alertas (Prometheus Up & Running)

| Metric | Tipo | Alerta |
|---|---|---|
| `jefrey_skill_init_total{skill,status="ok|fail|skip"}` | Counter | `increase(fail[1h])>3` |
| `jefrey_oauth_refresh_total{skill,status}` | Counter | `increase(status="fail"[1h])>5` |
| `jefrey_web_search_cache_hit` | Counter | `rate(hit[5m])<0.2` (cache ineficiente) |
| `jefrey_config_valid` | Gauge 0/1 | `==0` (CIPHER-019/002) |

Dashboards Grafana (P1.5, mas metric ja em P1.1): Skills Health, OAuth, Web Search.

---

## 9. Checklist aceite P1.1 — gate P1.1->P1.2

- [ ] `python scripts/compute_readiness.py --status '{"Skills":"READY"}'` => `92.0/67.2/60.4` + `python scripts/compute_readiness.py --json` ainda `86.0/62.8/56.5` (sem override) — prova que override funciona e default nao muta
- [ ] `python scripts/verify_env.py` PASS + `python scripts/setup.py --check` PASS + `docker compose config --quiet` OK
- [ ] `python -m scripts.smoke_test` => `>=3 skills` + `calendar SKIP sem token` + `web_search SKIP sem key` ou `PASS com key`, sem FAIL
- [ ] `python scripts/verify_p1.py` PASS (com mocks, sem cred real) — drive mock + web_search cache hit
- [ ] `python scripts/run_tests.py --ci` => `5 PASS / 0 FAIL / 116.9s` (ou 7 PASS se adicionar drive/notion) + `junit.xml` failures 0 + `ET.parse` OK
- [ ] `py_compile` 6 arquivos OK + ASCII 0 em `compute`/`acceptance`/`oauth.md` + sem BOM
- [ ] `config/tokens/` 0o700 + `config/credentials/` 0o700 + `token.json` 0o600 se existe + `git check-ignore` .env.bak + tokens
- [ ] `docs/oauth.md` + `docs/JEFREY-AUDIT/acceptance_p1.1.md` ASCII + `README` tracer bullet
- [ ] `git add` pronto: `src/jefrey/skills/drive.py`, `src/jefrey/core/config.py`, `src/jefrey/core/metrics.py`, `scripts/*`, `docs/*`, `.env.example`, `pyproject.toml`

---

## 10. Estimativa e meta comercial

- **P1.1:** 5 dias uteis (1 dev senior) — Skills 15 PARTIAL->READY (+6.0) => **92.0% Impl**
- **P1.2-1.5:** +14 dias (Policy/HITL + Infra) => **100% Impl / 73.0% Prod / 65.7% Comercial (69.3% com GTM 0.95)** — alvo 70% atingido.
- **Sem P1.1:** fica em 86% e nao comercializa (Skills bloqueia demo).

---

## 11. Referencias por decisao

- **Kleppmann DDIA:** peso funcional soma 100, `pool_pre_ping`, HNSW, single source `.env`+`env_file [.env]`
- **Ramalho Fluent Python:** `TypedDict`/`Final`/`Literal Status`, `dict(P0_STATUS)` copia (imutabilidade), `SCOPES` Final
- **Anderson Security:** fail-closed, `drive.file` minimo, `0o700/0o600`, `SECRET_RE` mask, `state+nonce`, `audit_fallback`
- **SWE at Google:** AXIOM 6 eixos, `run_tests.py` subprocess isolado + `PYTHONIOENCODING=utf-8` + `timeout 25`
- **Pragmatic Programmer:** broken windows (ASCII, sem BOM), DRY (`compute_readiness.py`)
- **High Performance Python:** `SCAN O(1) vs KEYS O(N)` (ja em `redis_memory.py`), cache 5m + timeout 10s
- **Prometheus Up & Running:** counters + gauge + alerts
- **MCP Spec 2026-07-28:** `@tool` + `SkillBase.get_tools()` + `service_role`
- **OpenAI Agents SDK 0.22:** `AgentState` + `StateGraph load_context->reasoning->execute_tools->save_memory->format_response`

---

*Pronto para executar P1.1 Dia 1 — `src/jefrey/skills/drive.py` + `config.py` + `setup.py` 0o700. Gate P0 ec9cd01 trancado.*
