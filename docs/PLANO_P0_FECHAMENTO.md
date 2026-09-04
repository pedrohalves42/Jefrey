# PLANO P0 — FECHAMENTO 100% COMERCIAL — 2026-09-03 20:45
> Base: main d970160 | 175/175 2x + 21/21 2x + 46 + 7/7 healthy + 633.58kB 891 modules | Axiom #1-7 + CIPHER 010/021/026/031/032/033/035 + Livros 1-10 + Sites CEOGPT/Julio/FatihMakes/Rahul

## 0. LEIA ISSO PRIMEIRO — ORDEM IDEAL

P0 fecha o que JÁ foi prometido em docs/PLANO_FEAT_UI_UI2.md 285L Definition of Done antes de qualquer voz/estética.
Não codar P1/P2/P3 antes de P0 verde — Ordem B: T3 P8 + T2 P7 + UI-2+UI-3 já provados local, falta só infra Ollama + burocracia tag/CI.
Tempo total P0: 30 min. Risco de quebrar 175/175: ZERO se seguir ordem abaixo.

---

## 1. OBJETIVO P0 — O QUE SIGNIFICA 100%

Leigo double-click `scripts/start_jefrey.bat` -> http://localhost:8000/ abre sem /docs, digita em Chat e recebe resposta 200 sem 401/500, Memory retorna 0..N com score p95 <300ms, Approvals e Observability sem loop 401. Gates provados 2x + CI remoto verde + tag v1.2.0-ui.

### 1.1 Inventário do que FALTA (extraído PLANO_FEAT_UI_UI2 Definition of Done — 14 caixas [ ])

| # | Item | Estado hoje d970160 | Falta |
|---|---|---|---|
| P0.1 | Chat POST /chat Bearer 200 | 500 Failed to connect to Ollama em pg_memory.py:211 embed_query -> ollama/_client.py:145 | ollama serve + pull nomic-embed-text |
| P0.2 | Memory GET /memory/search?q= vetorial 0..N p95 <300ms | 200 com secret mas embedding falha sem Ollama | mesmo Ollama |
| P0.3 | Approvals RBAC 403 guest | Silenciado 401 OK d970160, falta e2e admin vs guest | teste e2e |
| P0.4 | Observability 4 métricas vivas não-mock | /metrics 200 + Recharts mas sem assert | assert |
| P0.5 | Settings persiste sem reload | OK mas sem gate | gate |
| P0.6 | 100% comercial só http://localhost:8000/ | OK whitelist / + /assets/* + /vite.svg, mas start_jefrey.bat não existe | criar bat |
| P0.7 | Gates pós 175/175 2x 21/21 2x 46 guard 6/6 grafana editable false 7/7 | Local 100% OK, remoto CI d970160 não validado | validar actions |
| P0.8 | Tag v1.2.0-ui + CHANGELOG 1.2.0 | Parado v1.1.0 11c864c | tag + docs |

DoD fechado = todos acima verdes + live POST /chat 200. Falso positivo: chat 500 NÃO é bug DB (GET /memory/health 200 145 memories prova DB + compose postgres:5432 OK), é Ollama offline.

---

## 2. DIRETRIZES SEGMENTADAS — POR QUE CADA PASSO EXISTE

### 2.1 AXIOM #1-7 (FAIL-CLOSED)

| Axiom | Regra | Onde P0 aplica |
|---|---|---|
| #1 FAIL-CLOSED | negar por padrão, 401 sem Bearer, 500 não vaza stack | auth_middleware whitelist só / + /assets/* + /vite.svg; POST /chat 401 sem token, 500 Ollama com mensagem genérica "Erro interno" não vaza traceback |
| #2 ISOLAMENTO | user_id mandatory _build_filter + topic jefrey.events.{user_id} | pg_memory _build_filter(user_id=None) raise; Memory GET extrai request.state user_id não query |
| #3 SEM STUB EM PROD | JEFREY_ENV dev/prod validate_for_production() | ollama warmup só dev, prod exige real; dummy placeholder tvly***aqui não passa validate |
| #4 PERSISTÊNCIA REAL | Redis setex pipeline incr/expire, Postgres pgvector, não TTLCache prod | verify_p6_data 21/21 prova XADD maxlen10000 + DLQ maxlen5000 + pg_dump BGSAVE |
| #5 LEAST PRIVILEGE | overwrite False :ro CORS explicit allow_credentials False | compose :/app:ro read_only + tmpfs /app/.cache + StaticFiles só /assets hash |
| #6 CRIPTO | urlsafe_b64 without padding RS256+kid aud/iss/exp compare_digest | HMAC kid v1/v2 dual-verify eventbus |
| #7 1 PROGRAMA 7 PEÇAS | Vite build -> src/jefrey/static sem novo container | UI servida FastAPI StaticFiles html=True mount / depois routers |

### 2.2 CIPHER

| CIPHER | Regra | P0 |
|---|---|---|
| 010 audit | nunca logar token, redact_pii lru_cache 1024 + orjson | start.bat não echo $SECRET; Settings nunca console.log token |
| 021 silent except | zero except: pass | guard grep 6/6 C1a/C1b/C2/A1/A4/M5/A6 |
| 026 rate limiting | pipeline fail-closed | não tocar em P0, só re-validar |
| 031 OAuth2 JWKS | Bearer + introspect fallback | apiFetch authHeaders() Bearer |
| 032 Skill Risk | HITL RiskLevel LOW/MEDIUM/HIGH/CRITICAL deny UNKNOWN | Approvals 401->403 guest, decide só com token |
| 033 HMAC EventBus | kid v1/v2 dual-verify Redis Streams | não tocar, só verify 21/21 |
| 035 Token Refresh | TTLCache 1024/60 hash(token) compare_digest | auth_middleware |

### 2.3 LIVROS REF — MAPEAMENTO

| Livro | Capítulos P0 | Uso |
|---|---|---|
| 1 MCP Spec 2026-07-28 | tools/list + resources | MCP :8001 health |
| 2 OpenAI Agents Cookbook | agentes + HITL | Chat thread_id demo-1 |
| 3 Security Engineering Ross Anderson 3rd | cap8 auth | whitelist least privilege |
| 4 Prometheus Up & Running 2nd | cap5 cardinality cap6 histogram cap10 alerting cap11 Grafana | editable false schemaVersion 39 by(le) hits:2 + alerts 6 |
| 5 DDIA Kleppmann | cap3 Persistence cap5 Replication cap6 Partitioning cap12 Tuning | HNSW m16 ef64 p50 48ms p95 55ms SET LOCAL int(ef) CAST vector |
| 6 SWE at Google | cap8 Style cap14 Testing | deep 175/175 2x idempotente + compileall -q |
| 7 Fluent Python 19-21 | — | orjson + lru_cache (P7, não mexer) |
| 8 High Performance Python | cap1-4 | cProfile 7318886 calls 15.567s p7-cprofile.prof (P7, não mexer) |
| 9 Building LLM Applications | evals 6 types | FakeEmbed 768 md5 recall@5 0.7 (não mexer) |
| 10 Pragmatic Programmer | DRY | lib/api.ts helper único |

Ordem leitura P0: 1,2,3 -> DURANTE P8 4,5,6 -> DEPOIS 7,8,9,10 (já seguido)

### 2.4 SITES REFERÊNCIA — O QUE COPIAR SÓ DEPOIS DE P0 (P1-P3)

| Site | Conceito | Como entra depois | Por que NÃO agora |
|---|---|---|---|
| CEOGPT moritz.ceogpt.de/jarvis-aufbau | Gehirn Stimme Hand 4 Wochen Sprint Done-For-You 1-zu-1 WhatsApp 30 Tage | P1 Stimme Whisper+ElevenLabs wake porcupine jefrey; P2 Hand WhatsApp via n8n :5678 webhook | Sem P0 200 chat, voz não tem para onde falar |
| Julio vTIq4pUR7o0 N8N TEMPLATE GRATUITO | Drag-drop N8N flow | P2 export n8n/workflows/jarvis-n8n.json | n8n já healthy mas sem workflow versionado |
| FatihMakes Mark-LII LII | Voice Picker 5 vozes + Live Theming hue wheel + Reactive HUD pulse real audio + Boot chime 2.4s transform + Plugin System drop .py | P2 plugin_loader.py PluginRegistry + P3 theming hue | Quebraria 891 modules build |
| FatihMakes Mark-XXXIX-OR 39 | Advanced File Handling 500MB + Adaptive UI resizable + OpenRouter free-tier + Optimized Core 40% faster | P2 file upload + OpenRouter routing | Sem file upload ainda |
| Rahul x5ZIzhOqTzE Claude Code It Runs Everything | Agent controla OS inteiro | P2 skill shell com HITL CRITICAL | Sem HITL real ainda |

---

## 3. PLANO DETALHADO P0 — 7 PASSOS EM ORDEM (30 min)

### P0.1 — Ollama vivo + modelos (10 min)
**Objetivo:** Tirar chat de 500 Ollama -> 200.
**Diretriz:** Axiom #3 + Livro9 Building LLM Apps + Mark core/llm_client.py ensure_ollama_running() + warmup_model() KV priming.
**Livro:** HPP cap1 (KV cache priming system_prompt keep_alive -1 num_gpu 99 cai 17s -> <1s)
**Comandos PowerShell:**
```powershell
# 1. instalar se não tem: https://ollama.com/download -> ollama --version
ollama serve  # em terminal separado ou docker run -d -v ollama:/root/.ollama -p 11434:11434 ollama/ollama
ollama pull nomic-embed-text   # 274MB embedding 768d usado por pg_memory.py embed_query
ollama pull llama3.1:8b        # ou llama3.2 usado por Mark
ollama list
# 2. validar
curl.exe http://localhost:11434/api/tags
# compose já tem extra_hosts host.docker.internal:host-gateway para container enxergar 11434
```
**Gate:** `ollama list | findstr nomic-embed-text` + `curl 11434/api/tags 200`
**Rollback:** Se não quiser local, usar `JEFREY_LLM__API_KEY` OpenAI real — mas perde HNSW local.
**Prova:** docker logs jefrey-api para de mostrar `Failed to connect to Ollama`

### P0.2 — Prova viva Chat 200 + Memory 200 (5 min)
**Objetivo:** Fim do 500.
**Diretriz:** Axiom #1 FAIL-CLOSED + CIPHER-031 Bearer
**Comandos:**
```powershell
$s=(Select-String -Path .env -Pattern '^JEFREY_API__SECRET_KEY=').Line.Split('=',2)[1].Trim()
Invoke-RestMethod -Uri http://localhost:8000/chat -Method POST -Headers @{Authorization="Bearer $s";"Content-Type"="application/json"} -Body '{"message":"ola","thread_id":"demo-1"}' | ConvertTo-Json -Depth 4
# esperado: 200 {"response": "..."} não 500
$s | ForEach-Object { $h=@{Authorization="Bearer $s"}; Invoke-RestMethod -Uri "http://localhost:8000/memory/search?q=teste&limit=5" -Headers $h }
# esperado: 200 {"memories": [...], "count": N} p95 <300ms
```
**Gate:** `POST /chat 200 + GET /memory/search 200 + GET /memory/health 200 145 memories`
**Falso positivo:** sem token 401 é correto; com token 500 Ollama é infra não bug.

### P0.3 — Re-provar gates locais 2x (5 min)
**Diretriz:** SWE cap14 idempotente + DDIA cap6
**Comandos:**
```powershell
python scripts/_validate_deep.py; python scripts/_validate_deep.py  # deve 2x OKS: 175 WARNS: 0 BUGS: 0 100.0% 2x igual:true
python scripts/verify_p6_data.py; python scripts/verify_p6_data.py   # 21/21 100% DATA OK 2x
python -m compileall -q src; echo COMPILE_OK:$LASTEXITCODE          # 0
python -m pytest -q                                                  # 40 passed + evals 6 =46
docker compose config -q; echo CFG_OK:$LASTEXITCODE                  # 0
docker compose ps  # 7/7 healthy
```
**Gate:** Todos 100% iguais 2x. Se falhar, aborta tag.

### P0.4 — Validar CI remoto verde d970160 (2 min)
**Diretriz:** SWE cap14 CI gate + Livro4 cap11 Grafana
**Passos:** Abrir https://github.com/pedrohalves42/Jefrey/actions -> branch main d970160 -> workflow ci.yml -> ver jobs: guard 6/6 + pytest 40 + evals 6 + promtool 6/6 + grafana lint editable false. Local WSL `No such file` é esperado (bash só ubuntu-latest).
**Gate:** CI verde. Se vermelho, fix antes de tag.

### P0.5 — Criar scripts/start_jefrey.bat (3 min)
**Diretriz:** Pragmatic leigo + Mark Auto-Start registry/.desktop
**Conteúdo:**
```bat
@echo off
cd /d %~dp0..
docker compose up -d --wait
timeout /t 5
start http://localhost:8000/
echo Jefrey em http://localhost:8000/  Health http://localhost:8000/health  Grafana http://localhost:3000 admin/%GRAFANA_PASSWORD%
pause
```
**Gate:** double-click abre browser sem /docs, HealthBadge 7/7.

### P0.6 — Tag v1.2.0-ui + docs (5 min)
**Diretriz:** SWE cap8 + Keep a Changelog
**Comandos:**
```powershell
# atualizar TODO.md: [x] 1-6 + Estado final d970160 + prox tag
# atualizar CHANGELOG.md: ## [1.2.0] - 2026-09-03 - P0 100% comercial ...
git add TODO.md CHANGELOG.md scripts/start_jefrey.bat
git commit -m "chore(release): P0 100% comercial + start_jefrey.bat + CI verde -> v1.2.0-ui (Axiom 1, SWE cap14)"
git tag -a v1.2.0-ui -m "UI-2+UI-3 100% comercial 175/175 21/21 46 7/7 633kB healthy Ollama vivo"
git push origin main --tags
```

### P0.7 — Verificação final Definition of Done (2 min)
**Checklist:**
- [ ] http://localhost:8000/ 200 HTML sem token
- [ ] Settings colar JEFREY_API__SECRET_KEY 64 len + Save
- [ ] Chat digita -> 200 response (com Ollama)
- [ ] Memory busca -> 0..N score p95 <300ms
- [ ] Approvals sem token 0 requests (d970160) + com token lista 200
- [ ] Observability 4 métricas vivas + link Grafana :3000 admin/BGl-***TALZ
- [ ] Hard reload Ctrl+Shift+R carrega index-BA6ViX0G.js 633.58kB sem 401 loop
- [ ] docker compose ps 7/7 healthy 12+ min

---

## 4. SENHAS ENVOLVIDAS EM P0

| Var | Len | Uso em P0 |
|---|---|---|
| GRAFANA_PASSWORD BGl-***TALZ 16 | Grafana :3000 login admin |
| JEFREY_API__SECRET_KEY 7da4***a946 64 | Bearer Chat/Memory/Approvals prova 200 |
| JEFREY_DATABASE__PASSWORD 6 + JEFREY_REDIS__PASSWORD 17 | compose postgres:5432 redis:6379 já OK |
| JEFREY_EVENTBUS__HMAC* | não tocar, só verify 21/21 |

NUNCA logar plain (CIPHER-010). .env já gitignore.

---

## 5. COMANDOS PRONTOS COPIAR-COLAR (PowerShell)

```powershell
cd C:UsersPedrojarvis
ollama serve
# novo terminal
ollama pull nomic-embed-text; ollama pull llama3.1:8b; ollama list
$s=(Select-String -Path .env -Pattern '^JEFREY_API__SECRET_KEY=').Line.Split('=',2)[1].Trim()
Invoke-RestMethod -Uri http://localhost:8000/chat -Method POST -Headers @{Authorization="Bearer $s";"Content-Type"="application/json"} -Body '{"message":"ola","thread_id":"demo-1"}'
python scripts/_validate_deep.py; python scripts/_validate_deep.py
python scripts/verify_p6_data.py; python scripts/verify_p6_data.py
python -m compileall -q src; python -m pytest -q
docker compose ps; docker compose config -q
```

---

## 6. RISCOS E NÃO-ESCOPO P0

- NÃO fazer P1 voz / P2 plugins / P3 theming antes de P0 verde — invalida build 891 modules e perde 175/175 por changed files.
- NÃO trocar compose para :ro off ou N8N_BASIC_AUTH_ACTIVE true agora — fora de P0.
- Se ollama pull falhar (sem GPU), usa nomic-embed-text apenas (274MB) — chat usa llama3.1:8b opcional.
- Code-split 633kB >500kB warning é P3, não P0.

---

## 7. PRÓXIMO APÓS P0 VERDE

P1 Stimme (Whisper+ElevenLabs+porcupine + Chat mic HUD pulse), P2 Hand Plugins (plugin_loader + file upload 500MB + WhatsApp n8n + OpenRouter), P3 Estética CEOGPT (hue wheel + boot chime + code-split). Só após tag v1.2.0-ui push.

*Gerado 2026-09-03 20:45 a partir de TODO.md d970160 + PLANO_FEAT_UI_UI2 285L + Mark-LII 100k + Mark-XXXIX-OR 40598 + ceogpt.de — Axiom #1-7 CIPHER Livros 1-10.*
