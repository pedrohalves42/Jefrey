# PLANO MESTRE P0 COMPLETO — JEFREY 100% COMERCIAL — 2026-09-03 21:00
> main d970160 | 175/175 2x + 21/21 2x + 46 + 7/7 healthy (pre-pull) | Ollama nomic-embed-text 274MB dim768 + llama3.1:8b 4.9GB | Axiom #1-7 + CIPHER 010/021/026/031/032/033/035 + Livros 1-10 + Sites CEOGPT/Julio/FatihMakes/Rahul

## 0. INVENTARIO DE SENHAS — 18 SEGREDOS (MASCARADO 4***4 len=N) — NUNCA COMMIT .env PLAIN

> .env ja gitignore + docker-compose.yml usa ${VAR:?required} fail-closed (Axiom #1). Valores abaixo mascarados.

| # | Variavel | Onde | Uso | Estado | Len | Nota P0 |
|---|---|---|---|---|---|---|
| 1 | GRAFANA_PASSWORD | .env + compose:231 GF_SECURITY_ADMIN_PASSWORD | Grafana :3000 login admin / $GRAFANA_PASSWORD | SET required | 16 | BGl-***TALZ — por que pede login e Prometheus :9090 nao: GF_USERS_ALLOW_SIGN_UP false (UI com usuario) vs Prometheus scraper sem auth Livro4 cap10 |
| 2 | N8N_BASIC_AUTH_USER | .env + compose:175 | n8n :5678 Basic Auth user | SET | 6 | *** — hoje N8N_BASIC_AUTH_ACTIVE=false (desligado proposital P3b) |
| 3 | N8N_BASIC_AUTH_PASSWORD | .env + compose:176 | n8n password | SET | 17 | CHAN***PROD |
| 4 | N8N_API_KEY | .env | n8n 2.x REST API key | SET | 17 | CHAN***PROD |
| 5 | JEFREY_DATABASE__PASSWORD | .env + compose:15,66,123 POSTGRES_PASSWORD | Postgres jefrey-postgres:5432 | SET required | 6 | *** — curto, prod deve secrets.token_hex(16) |
| 6 | JEFREY_REDIS__PASSWORD | .env + compose:31,34,67,124 --requirepass | Redis 7.2 requirepass | SET required | 17 | jefr***2026 |
| 7 | JEFREY_API__SECRET_KEY | .env + compose:72 Bearer | Authorization: Bearer p/ /chat /memory /approvals | SET required | 64 | 7da4***a946 — usado no teste GET /memory/health 200 145 memories |
| 8 | JEFREY_EVENTBUS__HMAC_KEY | .env | EventBus kid v1 HMAC-SHA256 | SET | 64 | d5b7***84d2 |
| 9 | JEFREY_EVENTBUS__HMAC_KEYS_JSON | .env | Rotacao {"v1":..,"v2":..} dual-verify | SET | 145 | {"v1***44"} — Axiom #5 rotation |
| 10 | JEFREY_LLM__API_KEY | .env | LLM generico | placeholder | 17 | sk-s***aqui — trocar por real ou Ollama local |
| 11 | TAVILY_API_KEY | .env | web_search Tavily | placeholder | 19 | tvly***aqui |
| 12 | OPENAI_API_KEY | .env | OpenAI | placeholder | 17 | sk-s***aqui duplicado |
| 13 | ELEVENLABS_API_KEY | .env | TTS futuro P1 Stimme | placeholder | 20 | sua-***labs — precisa P1 |
| 14 | PICOVOICE_ACCESS_KEY / JEFREY_VOICE__WAKE_WORD__ACCESS_KEY | .env | Wake word porcupine jefrey | placeholder | 19 | sua-***oice — precisa P1 |
| 15 | JEFREY_VOICE__WAKE_WORD__KEYWORDS | .env | Keywords ["jefrey"] | SET | 10 | je***ey |
| 16 | JEFREY_INTEGRATIONS__NOTION__TOKEN | .env | Notion | placeholder | 10 | secr***_xxx |
| 17 | JEFREY_INTEGRATIONS__COMPOSIO__API_KEY | .env | Composio | placeholder | 18 | sua-***osio |
| 18 | JEFREY_OAUTH__CLIENT_SECRET | compose:79,136 ${:-} | OAuth opcional | vazio | 0 | OK dev, prod validate_for_production() exige |

**COMPOSE REFS VERIFICADOS:**
```
POSTGRES_PASSWORD: ${JEFREY_DATABASE__PASSWORD:?required} (15)
redis --requirepass ${JEFREY_REDIS__PASSWORD:?required} (31)
GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:?required} (231)
JEFREY_API__SECRET_KEY: ${JEFREY_API__SECRET_KEY} (72)
JEFREY_OAUTH__CLIENT_SECRET: ${JEFREY_OAUTH__CLIENT_SECRET:-} (79,136) vazio fail-open dev
```
**CIPHER-010:** audit.py redact_pii lru_cache 1024 + orjson — nunca loga token plain.

## 1. BASE FECHADA — NAO MEXER SEM BRANCH

- [x] T1 HARDENING + T3 P8 TAG v1.0.0 167/167 + T2 P7 PERF v1.1.0 175/175 + D5 push 11c864c + 3 tags v1.0.0/p5-c/v1.1.0
- [x] feat/cleanup-100 de2fe1f 93 obsoletos + fix ci.yml:52 grep '"editable": false'
- [x] feat/ui-shell 0339dd7 Vite+React+TS+Tailwind shadcn -> src/jefrey/static StaticFiles html=True mount / whitelist / + /assets/* + /vite.svg + reload=False tmpfs /app/.cache fix Watchfiles OS13
- [x] feat/ui-2 88f2685+1278674+be7b7e9 UI-2+UI-3 891 modules 633.58kB gzip 185.40kB + fix compose postgres:5432 redis:6379 sem fallback psycopg localhost + Memory GET q=&limit=
- [x] d970160 fix Approvals if(!getToken()) return silencia 401 polling GET /approvals?status=pending loop
- **GATES d970160:** deep 175/175 2x WARN0 BUG0 100% + verify 21/21 100% + compileall 0 + pytest 40 + evals 6 =46 + guard 6/6 + grafana editable false by(le) + ci grep OK + compose config -q RC0 + live / 200 HTML + /health 200 + /chat 401 fail-closed + with Bearer 500 Ollama (DB OK 145 memories)

## 2. DIRETRIZES SEGMENTADAS

### 2.1 AXIOM #1-7

| Axiom | Regra | P0 onde aplica |
|---|---|---|
| #1 FAIL-CLOSED | negar por padrao 401 sem Bearer, 500 nao vaza stack | auth_middleware whitelist SO / + /assets/* + /vite.svg; POST /chat 401 sem token, 500 Ollama msg generica |
| #2 ISOLAMENTO | user_id mandatory _build_filter + topic jefrey.events.{user_id} | pg_memory _build_filter(user_id=None) raise; Memory GET extrai request.state user_id |
| #3 SEM STUB EM PROD | JEFREY_ENV dev/prod validate_for_production() | ollama warmup so dev, prod exige real; placeholder tvly***aqui nao passa |
| #4 PERSISTENCIA REAL | Redis setex pipeline, Postgres pgvector, nao TTLCache prod | verify 21/21 XADD maxlen10000 DLQ maxlen5000 pg_dump BGSAVE |
| #5 LEAST PRIVILEGE | :ro CORS explicit allow_credentials False | compose :/app:ro read_only + tmpfs /app/.cache + StaticFiles so /assets hash |
| #6 CRIPTO | urlsafe_b64 without padding RS256+kid aud/iss/exp compare_digest | HMAC kid v1/v2 dual-verify |
| #7 1 PROGRAMA 7 PECAS | Vite build -> src/jefrey/static sem novo container | StaticFiles html=True mount / depois routers |

### 2.2 CIPHER

| CIPHER | Regra | P0 |
|---|---|---|
| 010 audit | nunca logar token redact_pii lru_cache 1024 + orjson | start.bat nao echo SECRET; Settings nunca console.log |
| 021 silent except | zero except: pass | guard 6/6 C1a/C1b/C2/A1/A4/M5/A6 |
| 026 rate limiting | pipeline fail-closed | re-validar |
| 031 OAuth2 JWKS | Bearer + introspect | apiFetch authHeaders Bearer |
| 032 Skill Risk | HITL RiskLevel deny UNKNOWN | Approvals 403 guest |
| 033 HMAC EventBus | kid v1/v2 dual-verify Streams | verify 21/21 |
| 035 Token Refresh | TTLCache 1024/60 hash(token) | auth_middleware |

### 2.3 LIVROS REF

| Livro | Caps P0 | Uso |
|---|---|---|
| 1 MCP Spec 2026-07-28 | tools/list | MCP :8001 health |
| 2 OpenAI Agents Cookbook | agentes HITL | Chat thread_id demo-1 |
| 3 Security Engineering 3rd | cap8 | whitelist least privilege |
| 4 Prometheus Up&Running 2nd | cap5 cardinality cap6 histogram cap10 alerting cap11 Grafana | editable false schema39 by(le) hits2 6 alerts |
| 5 DDIA | cap3 Persistence cap12 Tuning | HNSW m16 ef64 p50 48ms p95 55ms SET LOCAL int(ef) CAST vector |
| 6 SWE at Google | cap8 Style cap14 Testing | deep 175/175 2x idempotente compileall -q |
| 7 Fluent Python | 19-21 | orjson+lru_cache (P7 nao mexer) |
| 8 High Performance Python | cap1-4 | cProfile 7318886 calls 15.567s (P7) |
| 9 Building LLM Apps | evals 6 types | FakeEmbed 768 md5 recall@5 0.7 |
| 10 Pragmatic Programmer | DRY | lib/api.ts helper unico |

### 2.4 SITES — O QUE COPIAR SO DEPOIS DE P0 (P1-P3)

| Site | Conceito | Como entra depois | Por que NAO agora |
|---|---|---|---|
| CEOGPT moritz.ceogpt.de | Gehirn Stimme Hand 4 Wochen Done-For-You WhatsApp | P1 Stimme Whisper+ElevenLabs wake + P2 Hand WhatsApp via n8n | sem P0 200 chat voz nao tem onde falar |
| Julio vTIq4pUR7o0 N8N TEMPLATE | Drag-drop N8N flow | P2 export n8n/workflows/jarvis-n8n.json | n8n healthy mas sem workflow |
| LII personalization | Voice Picker 5 + Theming hue wheel + HUD pulse real audio + Boot 2.4s + Plugin System | P3 theming + P2 plugin_loader PluginRegistry | quebraria build 891 |
| XXXIX-OR 39 | File upload 500MB + Adaptive UI + OpenRouter free + 40% faster | P2 file upload + OpenRouter | sem upload ainda |
| Rahul Claude Code | It Runs Everything OS control | P2 skill shell HITL CRITICAL | sem HITL real |

## 3. PENDENTES PLANO_FEAT_UI_UI2 285L DoD (14 caixas [ ])

- Chat Bearer 200 (hoje 500 Ollama), Memory vetorial p95 <300ms, Approvals RBAC 403 e2e, Observability 4 metricas vivas, Settings persiste, 100% comercial so / (bat agora criado), TS strict guard 6/6, Gates 175/175 2x + CI remoto verde d970160 + tag v1.2.0-ui CHANGELOG 1.2.0

## 4. PLANO P0 7 PASSOS 30min — ORDEM IDEAL SEM QUEBRAR + O QUE CODAR/CONSERTAR/CONSTRUIR

### P0.1 Ollama vivo 10m — CODAR nada, CONSERTAR infra, CONSTRUIR modelos
- ollama serve + pull nomic-embed-text 274MB dim768 OK + llama3.1:8b 4.9GB OK + warmup KV keep_alive -1 num_gpu99 (Mark core/llm_client ensure_ollama_running). Gate ollama list 2 models + curl 11434/api/tags 200 + curl 11434/api/embed dim768 OK ja provado. HPP cap1 17s-><1s.

### P0.2 Prova Chat/Memory 200 5m — CONSERTAR 500->200
- curl POST /chat + GET /memory/search?q=teste Bearer JEFREY_API__SECRET_KEY 64 len. Hoje Failed to connect Ollama — agora com nomic deve 200. Axiom #1 401 sem token continua correto. Guardar p95 log.

### P0.3 Re-provar gates 5m — CONSTRUIR provas
- deep 175/175 2x + verify 21/21 2x + compileall 0 + pytest 40+evals6=46 + grafana editable false by(le) 2 + ci grep ok + compose config -q RC0 + docker 7/7 healthy. Ja 175/175 2x durante pull.

### P0.4 CI remoto 2m — VERIFICAR
- https://github.com/pedrohalves42/Jefrey/actions main d970160 guard 6/6 verde (bash so ubuntu-latest).

### P0.5 start_jefrey.bat 3m — CONSTRUIR leigo
- double-click -> docker compose up -d --wait + start http://localhost:8000/ (equiv Mark Auto-Start). Conteudo ja escrito scripts/start_jefrey.bat.

### P0.6 Tag v1.2.0-ui 5m — CODAR docs
- TODO.md [x]1-6 + CHANGELOG 1.2.0 + git tag -a v1.2.0-ui + push --tags

### P0.7 DoD final 2m — VERIFICAR leigo
- / 200 HTML sem token + Settings Save + Chat 200 + Memory 0..N p95 <300ms + Approvals 0 req sem token + Observability 4 metricas + HealthBadge 7/7 + hard reload BA6ViX0G.js

## 5. O QUE DEVEMOS MELHORAR — 14 ITENS MINUCIOSOS COM DETALHE

| # | Melhoria | Detalhe explica tudo | Esforco | Risco 175 |
|---|---|---|---|---|
| 1 | Ollama warmup KV cache priming | Mark warmup_model(system_prompt) keep_alive -1 num_gpu99 — sem isso first token 17s, com  <1s. Copiar Mark core/llm_client.py warmup para src/jefrey/core/llm_client.py. | 10m | 0 |
| 2 | start_jefrey.bat leigo | Mark Auto-Start registry/.desktop — leigo hoje precisa docker compose manual. Bat ja criado, falta testar double-click. | 5m | 0 |
| 3 | Silenciar 401 Observability | d970160 silenciou Approvals, falta Observability /metrics 401 guard — mesmo if(!getToken()) return. | 5m | 0 |
| 4 | Voz STT+TTS+wake porcupine jefrey + Chat mic HUD pulse | Gap 100% vs todos videos. Whisper.cpp STT + ElevenLabs TTS (ELEVENLABS_API_KEY placeholder) + porcupine wake jefrey (PICOVOICE). Chat button MediaRecorder -> POST /stt -> /chat -> TTS play + waveform pulse real audio Mark LII. | 60m | medio |
| 5 | Plugin System drop .py | Mark core/plugin_loader.py PluginRegistry _NAME_RE ^[a-z_][a-z0-9_]{0,63}$ collision detection discover_plugins() + list_for_ui(). src/jefrey/plugins/ + _template.py sem tocar core. | 40m | medio |
| 6 | File upload 500MB | XXXIX Advanced File Handling + dashboard/server.py _make_uploads_dir() + MAX_UPLOAD_MB 500 + POST /files/upload. | 20m | baixo |
| 7 | OpenRouter free-tier | XXXIX 5 actions route via OpenRouter free-tier aumenta limite sem custo, Gemini Live continua voz. | 15m | baixo |
| 8 | WhatsApp via n8n webhook | CEOGPT Hand + Mark send_message.py pyautogui/_desktop_send WhatsApp/Telegram. n8n :5678 ja healthy, criar /webhook/whatsapp com HMAC. | 20m | baixo |
| 9 | Theming hue wheel + Reactive HUD + Boot chime | LII personalization: Settings hue wheel hex instant across every panel CSS var --primary hsl($hue) + reactor pulse real audio + boot 2.4s synthesized no file + toggle. | 30m | baixo |
| 10 | Code-split 633kB | Build warning 633kB >500k vite.config.ts manualChunks vendor/react recharts + ui/shadcn HPP cap1. | 10m | 0 |
| 11 | Undo/Confirm CRITICAL | Mark core/undo.py 4451 stack move/rename/create + core/confirm.py 5739 shutdown/WiFi button you press -> PolicyEngine RiskLevel CRITICAL. | 20m | baixo |
| 12 | N8N template export | Julio TEMPLATE GRATUITO marketing — export n8n/workflows/jarvis-n8n.json versionado. | 10m | 0 |
| 13 | Trocar DB password 6 len -> 32 hex | validate_for_production() prod exige forte — secrets.token_hex(16). | 5m | 0 |
| 14 | Ligar N8N_BASIC_AUTH_ACTIVE true quando expor | Seguranca — hoje false proposital local, ligar ao expor :5678. | 2m | 0 |

Total backlog ~4h pos-P0.

## 6. STATUS P0 AGORA 21:00 — DOCKER TRAVOU NO PULL 4.9GB

Ollama OK 2 models dim768, gates OK 175/175 2x 21/21 compile 0 pytest 40, bat OK, grafana OK, compose config CFG_OK.
Docker engine 500 _ping apos pull: com.docker.service STOPPED code 1077 + wsl --shutdown tentado + ports 8000/11434 ainda LISTENING PID 21072 com.docker.backend mas GET /health timeout. Ollama 11434/api/tags OK 200. Netstat 8000 LISTENING mas /health nao responde — engine precisa restart manual Docker Desktop.

PROXIMO MANUAL 2min: Docker Desktop -> Restart (tray -> Restart) -> cd C:\Users\Pedro\jarvis && docker compose up -d --wait -> curl http://localhost:8000/health -> entao chat 200 -> tag.

COMANDOS POS-RESTART:
```powershell
cd C:\Users\Pedro\jarvis
docker compose up -d --wait; docker compose ps
$s=(Select-String -Path .env -Pattern '^JEFREY_API__SECRET_KEY=').Line.Split('=',2)[1].Trim()
Invoke-RestMethod -Uri http://localhost:8000/chat -Method POST -Headers @{Authorization="Bearer $s";"Content-Type"="application/json"} -Body '{"message":"ola","thread_id":"demo-1"}'
```

*Gerado de leitura real TODO.md d970160 + PLANO_FEAT_UI_UI2 285L + Mark-LII 100k + XXXIX-OR 40598 + ceogpt.de + .env + compose — Axiom CIPHER Livros.*
