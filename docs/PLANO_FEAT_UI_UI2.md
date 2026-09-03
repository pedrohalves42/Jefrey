# PLANO FEAT/UI — UI-1 + UI-2 + UI-3 (100% comercial) — 2026-09-03 18:43
> **Axiom #1-7 + CIPHER 010/021/025/026/028/029/031/032/033/035 + Livros 1-10 (ordem 1,2,3 -> 4,5,6 -> 7,8,9,10) + 175/175 + 21/21 + 7/7 healthy**
> Base: `main db53a2d` (feat/ui-shell 0339dd7 merged — UI-1 Shell 200 HTML, /chat 401, 175/175 2x, 21/21 2x, 46 testes, 7/7 healthy)
> Branch alvo: `feat/ui-2` (a partir de main) -> UI-2 90m -> merge -> `feat/ui-3` 60m -> 100% comercial

---

## 0. DIAGNOSTICO REAL (lido em disco agora)

### Estado validado
- **main db53a2d** = 0069418 merge feat/ui-shell + db53a2d chore TODO — 34 files +3709 (ui/ + src/jefrey/static/ + api/main.py + auth + compose)
- **Gates**: deep 175/175 WARN0 BUG0 2x + verify 21/21 2x + compileall OK + pytest 40 + evals 6 =46 + guard 6/6 + grafana editable false + by(le) + ci grep `"editable": false` OK
- **Docker**: 7/7 (jefrey-api 16m healthy, postgres 25h healthy, redis 9h healthy, mcp/prometheus healthy, grafana/n8n running) + compose config -q RC0 + .env + tmpfs /app/.cache + reload=False
- **Live**: GET /health 200 + GET / 200 HTML + GET /docs 200 + POST /chat 401 fail-closed + /assets 200
- **UI-1 Shell**: Vite 5.4.21 + React 18 + TS 5.5 + Tailwind 3.4 + shadcn + React Query + Recharts -> build 93 modules 233kB gzip 74kB -> src/jefrey/static via StaticFiles mount / html=True (parent.parent fix)

### O que existe em ui/src agora
- **App.tsx**: BrowserRouter + QueryClientProvider + header "Jefrey 1 programa 7 pecas 175/175 + 21/21" + Nav + HealthBadge (/health 10s) + Routes 5 paginas
- **Chat.tsx**: stub fetch POST /chat thread_id demo-1 com fallback "Sem conexao :8000"
- **Memory.tsx**: stub com curl exemplo + nota p50 48ms p95 55ms HNSW
- **Approvals/Observability/Settings**: stubs 9-18 linhas cada
- **pkg**: react 18.3.1, react-router-dom 6.26.2, tanstack/query 5.51.0, recharts 2.12.7 — 181 pacotes 4 vulns
- **Vite**: proxy /health|/chat|/memory|/approvals|/metrics -> :8000, outDir ../src/jefrey/static emptyOutDir true
- **Static**: src/jefrey/static/index.html 0.49kB + assets js/css existe

### Contratos API reais (main.py + auth)
- **PUBLIC sem auth** (Axiom #5 least privilege + CIPHER-019): /health, /docs, /openapi.json, /redoc, /metrics, / (html), /vite.svg, /favicon.ico, /assets/* — resto 401
- **Protegidos 401**: /chat, /memory, /approvals (+ Bearer secret ou introspect JWKS RS256 kid)
- **Middleware**: FastAPIAuthMiddleware fail-closed — TTLCache 1024/60 hash(token) compare_digest, _PUBLIC_PATHS + _PUBLIC_PREFIXES (/assets/)
- **StaticFiles**: app.mount("/", StaticFiles(directory=src/jefrey/static, html=True), name="ui-static") DEPOIS das rotas — ordem importa

---

## 1. VISAO E DIRETRIZES (por que UI nao e "8a peca")

### Axioma #1 — 1 programa 7 pecas
> Jefrey = 1 programa com 7 pecas (api, mcp, postgres pgvector, redis, n8n, prometheus, grafana). UI e **pele** do mesmo programa, servida por FastAPI StaticFiles em /, **sem novo container** (rejeitado Next.js separado). Prova: src/jefrey/static versionado, Docker sem npm, 7/7 continua 7/7.

### 7 Axiomas aplicados a UI
1. **FAIL-CLOSED**: sem token -> 401 + mensagem humana "faca login em /settings" (nunca mock silencioso) — 401 preservado
2. **ISOLAMENTO**: todo POST leva `user_id` (sem default system) + `_build_filter` mandatory — UI envia user_id do Settings/localStorage, nunca hardcode
3. **SEM STUB EM PROD** (JEFREY_ENV dev/prod + validate_for_production): UI mostra badge ENV + erro se prod sem token (CIPHER-031)
4. **PERSISTENCIA REAL**: Chat/Memory nao usam localStorage como DB — so cache de exibicao, verdade em Postgres/Redis
5. **CRIPTO**: Bearer via Authorization header, nunca URL query; kid v1/v2 dual-verify ja em api (CIPHER-033)
6. **LEAST PRIVILEGE** (overwrite=False, CORS explicit): whitelist /assets/* hash, nao /*; HealthBadge sem credenciais
7. **OBSERVABILIDADE SEM HIGH CARDINALITY**: /metrics sem user_id label (Livro 4 cap5 <800 series), UI so le agregados

### CIPHERS que tocam UI
- **031 OAuth2 JWKS/introspect**: UI Settings testa JWKS urlsafe + RS256 + aud/iss/exp + kid rotation v1->v2
- **032 Skill Risk**: PolicyEngine guest/user/admin + HITL RiskLevel — Approvals so libera LOW auto, MEDIUM+ exige HITL
- **033 HMAC EventBus**: kid v1/v2 dual-verify — UI nunca assina, so exibe status via /health
- **035 Token Refresh**: UI chama /auth/refresh com httpx real + timeout, nunca dev-auto-generated-key (C1a)
- **026 Rate Limit pipeline fail-closed**: UI exibe 429 com Retry-After, nao retry infinito
- **028/029 Policy**: RBAC refletido na Nav (guest so Chat/Memory, admin ve Approvals)
- **021 Silent except**: UI loga erro com redact_pii (CIPHER-010 audit canonical sort_keys) sem `except: pass`
- **010 Audit**: todo POST /chat gera trilha user_id + thread_id (orjson sort_keys)
- **025 Dual-write**: UI indica "eventual consistency" se 202

### Livros — ordem de leitura durante feat/ui
- **AGORA (1,2,3)**: MCP Spec 2026-07-28 (tool calling), OpenAI Agents Cookbook (thread pattern), Security Engineering 3rd (cap8 auth, cap10 least priv) — guiam UI-2 Chat
- **DURANTE P8/UI (4,5,6)**: Prometheus Up & Running 2nd cap5 cardinality + cap10/11 Grafana/SLO (Observability), DDIA cap12 HNSW tuning p95, SWE at Google cap8 Style + cap14 Testes
- **DEPOIS (7,8,9,10)**: Fluent Python 19-21 (async), High Perf Python cap1-4 (cProfile ja feito), Building LLM Apps 2024 (evals 6 tipos), Pragmatic Programmer 20th (DRY)

---

## 2. ESCOPO FECHADO — O QUE E UI-1 / UI-2 / UI-3

| Fase | Tempo | Entrega | Estado | Gates |
|------|-------|---------|--------|-------|
| **UI-1 Shell** | 45m | Vite+React+TS+Tailwind+shadcn, 5 telas stubs, HealthBadge 10s, StaticFiles mount, whitelist /assets | FECHADO 3fa9be3..0339dd7 -> main db53a2d | 175/175 2x + 21/21 2x + 46 + 7/7 |
| **UI-2 Chat+Memory** | **90m** | Chat real + Memory vetorial p50 48ms | PROXIMO feat/ui-2 | manter 175/175 + 21/21 + 7/7 + CI verde |
| **UI-3 HITL+Obs** | **60m** | Approvals HITL + Observability live + Settings auth | depois UI-2 | idem + 100% comercial |
| **Total** | **195m** | 75% -> 100% comercial sem quebrar |  |  |

### UI-1 ja entregue (nao refazer)
- Build 93 modules, HealthBadge, Nav, 5 rotas, static em src/jefrey/static, 401 preservado

### UI-2 — Chat real + Memory vetorial (90m) — DETALHE
**Objetivo**: leigo abre http://localhost:8000/ e conversa + busca memoria sem abrir /docs

#### Chat (45m)
- **UX**: input + lista msgs (user/assistant) + thread_id persistido localStorage (demo-1 default) + Enter envia + loading spinner + erro 401/429/500 humano
- **API**: `POST /chat` body `{message, thread_id, user_id}` + header `Authorization: Bearer <token>` (Settings/localStorage). Sem token -> 401 + botao "Ir para Settings"
- **Axioms**: #2 user_id obrigatorio, #1 fail-closed, CIPHER-031/032
- **Livros**: OpenAI Agents Cookbook (thread pattern) + Security Eng cap8
- **Arquivo**: `ui/src/pages/Chat.tsx` (33 linhas hoje -> ~120 linhas) + helper `ui/src/lib/api.ts`
- **Estados**: idle | loading | error (401|429|500) | success — sem silent except

#### Memory (45m)
- **UX**: input query + botao Buscar + lista resultados (tipo, conteudo, score, created_at) + badges episodic/semantic/procedural + p95 nota "HNSW m16 ef64 p50 48ms p95 55ms"
- **API**: `POST /memory/search` body `{query, user_id, limit?:5, layer?:episodic}` + Bearer -> `{results: [{content, metadata, score}]}`
- **Axioms**: #2 _build_filter user_id mandatory (pg_memory.py), #4 persistencia real, DDIA cap12 HNSW ef_search 64 default
- **Arquivo**: `ui/src/pages/Memory.tsx` (10 linhas hoje -> ~110 linhas)
- **Perf**: p95 <300ms SLO (ja 55ms ef64) — UI mostra latencia X-Response-Time se api expor

#### Criterios UI-2 DONE
- [ ] Chat envia e recebe com Bearer real (200 com token, 401 sem)
- [ ] Memory busca vetorial retorna 0..N com score, sem vazar user_id
- [ ] TS strict sem any novo, sem except: pass (SWE cap8)
- [ ] HealthBadge + Nav intactos, / continua 200 HTML
- [ ] Gates apos: deep 175/175 2x + verify 21/21 2x + pytest 46 + compileall + guard 6/6 + docker 7/7 + compose config -q RC0

### UI-3 — HITL Approvals + Observability + Settings (60m) — RESUMO
**Objetivo**: operador humano aprova tool critica + ve SLOs vivos

#### Approvals HITL (20m)
- **UX**: tabela pending/approved/rejected via `GET /approvals?status=pending` + botoes Approve/Reject (POST /approvals/{id}/decision) — so admin (CIPHER-032)
- **Policy**: guest/user nao ve botao, Badge por RiskLevel LOW/MEDIUM/HIGH/CRITICAL
- **Arquivo**: `ui/src/pages/Approvals.tsx`

#### Observability (20m)
- **UX**: 4 cards Recharts lendo `/metrics` (texto) + polling 15s: API error rate, RateLimit denials, Kid legacy, Memory p95 — sem user_id label (Livro 4 cap5)
- **Grafana link**: botao "Abrir Grafana :3000" (jefrey-main 8 panels editable false)
- **Arquivo**: `ui/src/pages/Observability.tsx`

#### Settings (20m)
- **UX**: campo Bearer token (salva localStorage, nunca loga) + seletor user_id + badge ENV (dev/prod) + botao Testar /health com token + link /docs
- **Arquivo**: `ui/src/pages/Settings.tsx` — unico lugar que toca localStorage token

#### Criterios UI-3 DONE
- [ ] Approvals lista + aprova/rejeita com RBAC (403 se guest)
- [ ] Observability mostra 4 metricas vivas (nao mock)
- [ ] Settings persiste token e habilita Chat/Memory sem recarregar
- [ ] 100% comercial: leigo usa so http://localhost:8000/ sem /docs

---

## 3. PLANO DE EXECUCAO — ORDEM IDEAL (Axiom #1 FAIL-CLOSED)

### Pre-condicoes (ja provadas 18:08 — nao pular)
1. main db53a2d 175/175 2x + 21/21 2x + 46 + 7/7 healthy + / 200
2. Branch a partir de main (nunca codar direto em main)
3. CI local guard 6/6 + promtool + pytest antes de commit (SWE cap14 idempotente)

### Passo a passo UI-2 (90m cronometrado)
| # | Min | Acao | Axiom/Cipher/Livro | Prova |
|---|-----|------|---------------------|-------|
| 0 | 5 | `git checkout -b feat/ui-2` a partir de main db53a2d + `npm --version && node --version` | Axiom #1 proteger main | git log -3 |
| 1 | 10 | Criar `ui/src/lib/api.ts` helper fetch com Bearer + user_id + error mapping 401/429/500 | CIPHER-031, Livro 6 cap8 Style | arquivo 40 linhas |
| 2 | 30 | Chat.tsx real: input controlado + useState msgs + POST /chat + thread_id localStorage + loading + 401 CTA Settings | Axiom #1/#2, Livro 2 Agents | curl + UI manual |
| 3 | 30 | Memory.tsx real: query + POST /memory/search + lista + badges tipo/score + nota HNSW | Axiom #2/DDIA cap12, Livro 5 | bench p95 55ms |
| 4 | 15 | Polish: a11y, tailwind responsivo, shadcn Card/Badge, build `npm run build` -> src/jefrey/static | Livro 6 cap8, HPP cap1 | build 93 modules OK |

### Passo a passo UI-3 (60m — apos UI-2 merge)
| # | Min | Acao | Axiom/Cipher/Livro | Prova |
|---|-----|------|---------------------|-------|
| 5 | 20 | Approvals.tsx: GET /approvals + tabela + POST decision + RBAC guard | CIPHER-032 HITL | 403 guest OK |
| 6 | 20 | Observability.tsx: fetch /metrics parse + Recharts 4 cards + polling 15s + link Grafana | Livro 4 cap5/10/11 | metrics sem user_id |
| 7 | 20 | Settings.tsx: input token + localStorage + Testar auth + ENV badge | CIPHER-031, Livro 3 cap8 | token nunca logado |

### Validacao apos cada UI (15m — sem pular, Axiom #1)
```powershell
cd C:\Users\Pedro\jarvis
python scripts/_validate_deep.py        # 175/175 2x
python scripts/verify_p6_data.py        # 21/21 2x
python -m compileall -q src && echo COMPILE_OK
python -m pytest -q                     # 40 + evals 6 =46
docker compose config -q && echo CFG_OK
docker compose ps                       # 7/7 healthy
curl.exe http://localhost:8000/         # 200 HTML
curl.exe http://localhost:8000/health   # 200 {"status":"ok"}
```
So merge --no-ff se tudo PASS + CI remoto verde (https://github.com/pedrohalves42/Jefrey/actions)

### Git flow
```bash
git checkout main && git pull --ff-only origin main  # db53a2d
git checkout -b feat/ui-2
# ... codar UI-2 90m + gates 15m ...
git add ui/ src/jefrey/static/ && git commit -m "feat(ui): UI-2 Chat real + Memory vetorial (Bearer + user_id, p95 55ms, Axiom 1/2, CIPHER-031)"
git push -u origin feat/ui-2
# esperar CI verde (guard 6/6 + pytest 40 + promtool + grafana editable)
git checkout main && git merge --no-ff feat/ui-2 -m "merge(feat/ui-2): Chat+Memory 175/175 21/21 7/7" && git push origin main
# repetir para feat/ui-3
```

---

## 4. RISCOS E MITIGACOES (Axioms)

| Risco | Prob | Impacto | Mitigacao (Axiom) | Livro |
|-------|------|---------|-------------------|-------|
| Quebrar 401 em / (voltar 401) | media | alto | manter _PUBLIC_PATHS + _PUBLIC_PREFIXES, testar TestClient / 200 antes de commit | Security Eng cap8 |
| Vazar user_id (isolation) | alta | critico | nunca default user_id, UI exige Settings user_id, backend _build_filter mandatory (Axiom #2) | DDIA cap6 |
| High cardinality /metrics | baixa | alto | UI nao cria label user_id, so le agregados (Livro 4 cap5 <800 series) | Prometheus cap5 |
| Mock em prod (valid_ prefix) | media | critico | JEFREY_ENV dev/prod gate, UI mostra ENV, teste com token real (CIPHER-035) | SWE cap14 |
| Build quebrar por TS strict | media | medio | fix tsconfig composite true + emitDeclarationOnly ja feito, manter | SWE cap8 |
| npm vulns 4 (recharts) | baixa | medio | audit fix so se nao quebrar build, nao bloquear UI-2 | — |
| Watchfiles Permission denied OS13 | ja fixado | alto | reload=False + tmpfs /app/.cache ja em compose, nao reverter | HPP cap1 DDIA cap3 |

---

## 5. MAPEAMENTO LIVROS -> TAREFAS

| Livro | Cap | Onde usa em feat/ui |
|-------|-----|---------------------|
| 1 MCP Spec 2026-07-28 | tools/list, call | Chat thread_id pattern, tool risk (Approvals) |
| 2 OpenAI Agents Cookbook | state, memory | Chat state msgs + Memory search/add |
| 3 Security Engineering 3rd | cap8 auth, cap10 priv | whitelist /assets, Bearer nunca URL, RBAC |
| 4 Prometheus Up & Running 2nd | cap5 cardinality, cap10/11 Grafana/SLO | Observability 4 cards, <800 series, by(le) |
| 5 DDIA | cap3 persistencia, cap12 tuning | HNSW m16 ef64 p95 55ms, pgvector 768 dim |
| 6 SWE at Google | cap8 Style, cap14 Testing | TS strict, guard 6 greps, 2x idempotente, pre-commit |
| 7 Fluent Python | 19-21 async | (depois) orjson + lru_cache ja feito |
| 8 High Perf Python | cap1-4 | cProfile 7318886 calls ja, bench 60 queries |
| 9 Building LLM Apps | 2024 | evals 6 tipos recall@5 0.7 ja |
| 10 Pragmatic Programmer | DRY | api.ts helper unico, nao duplicar fetch |

---

## 6. DEFINITION OF DONE — 100% COMERCIAL

### UI-1 (ja)
- [x] `http://localhost:8000/` 200 HTML sem token + HealthBadge 7/7 + 5 rotas + build 74kB gzip

### UI-2 (para fechar)
- [ ] Chat POST /chat com Bearer real funciona (leigo digita e recebe resposta)
- [ ] Memory POST /memory/search vetorial 0..N com score, p95 <300ms
- [ ] 401 sem token com CTA "Ir para Settings" (fail-closed humano)
- [ ] Gates apos: deep 175/175 2x + verify 21/21 2x + 46 + compileall + guard + 7/7 + compose RC0 + / 200 + /chat 401 + with Bearer !=401

### UI-3 (para 100%)
- [ ] Approvals HITL lista + approve/reject com RBAC (guest 403)
- [ ] Observability 4 metricas vivas Recharts + link Grafana :3000
- [ ] Settings persiste token/user_id e desbloqueia Chat/Memory
- [ ] Leigo usa so double-click `scripts/start_jefrey.bat` -> http://localhost:8000/ sem /docs
- [ ] CI remoto verde em main (guard 6/6 + pytest 40 + evals 6 + promtool 6/6 + grafana editable false)

### Gates finais (antes de tag v1.2.0-ui)
```
deep 175/175 2x  WARN0 BUG0  98-99% codigo OK
verify 21/21 2x 100% DATA OK
pytest 40 + evals 6 =46 passed
compileall OK
guard 6/6 PASS
grafana editable false + by(le) true + ci grep ok
docker 7/7 healthy + compose config -q RC0
live: / 200 HTML, /health 200, /docs 200, /chat 401, /memory 401, with Bearer 200
```

---

## 7. COMANDOS PRONTOS (copiar-colar PowerShell)

```powershell
# 0. partir de main limpo
cd C:\Users\Pedro\jarvis
git checkout main; git pull --ff-only origin main; git log --oneline -3
git checkout -b feat/ui-2
npm --version; node --version  # 11.7.0 v24.19.0

# 1. codar UI-2 (Chat + Memory) — 90m
# editar ui/src/lib/api.ts, ui/src/pages/Chat.tsx, ui/src/pages/Memory.tsx
cd ui; npm run build; cd ..
# build gera src/jefrey/static 93 modules

# 2. validar 15m (sem pular)
python scripts/_validate_deep.py; python scripts/_validate_deep.py
python scripts/verify_p6_data.py; python scripts/verify_p6_data.py
python -m compileall -q src; echo COMPILE_OK
python -m pytest -q
docker compose config -q; echo CFG_OK
docker compose ps
curl.exe http://localhost:8000/; curl.exe http://localhost:8000/health

# 3. commit + push
git add ui/ src/jefrey/static/ ui/src/lib/api.ts
git commit -m "feat(ui): UI-2 Chat real + Memory vetorial p50 48ms (Axiom 1/2, CIPHER-031, DDIA cap12)"
git push -u origin feat/ui-2
# ver CI: https://github.com/pedrohalves42/Jefrey/actions

# 4. merge quando CI verde
git checkout main; git merge --no-ff feat/ui-2 -m "merge(feat/ui-2): Chat+Memory -> 175/175 21/21 7/7" ; git push origin main
```

---

## 8. PROXIMO PASSO IMEDIATO (agora)

1. **Este plano** salvo em `docs/PLANO_FEAT_UI_UI2.md` — commit em main como docs (sem codigo) ou deixar para feat/ui-2. **Recomendado**: commit docs em main agora (db53a2d -> docs/plano) com guard, depois branch feat/ui-2 parte desse docs.
2. Criar `feat/ui-2` e executar passo 1-4 acima (90m) mantendo 175/175.
3. Nao tocar em 10 repos externos (public-apis etc) — ja avaliado, nao ajuda UI-2 (sao APIs/awesome lists).

---

*Gerado 2026-09-03 18:43 a partir de leitura real de TODO.md, App.tsx, Chat.tsx, Memory.tsx, main.py, auth_middleware.py, compose, ci, pkg, vite — Axiom #1 FAIL-CLOSED, CIPHER, Livros 1-10, 175/175 21/21 7/7.*
