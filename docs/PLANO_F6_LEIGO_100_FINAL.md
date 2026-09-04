# PLANO F6 — LEIGO 100% + INTERFACE CEOGPT + CONEXÕES — 2026-09-04 17:14

> **Branch base:** `main` `82c56ef` + tag `v1.4.0-final-100` SYNCED origin — deep 175/175 2x WARN0 BUG0 + 21/21 2x + 27/27 2x 9 panels by(le) editable false + 54/54 2x + pytest 40 2x + live 16/16 (health/metrics/vite/openapi/prometheus/grafana anon401/auth200/ollama qwen2.5 dev-token chat poll 48s stt/tts 6 voices) + 7/7 healthy + guard 6/6 + compileall OK
> **Objetivo:** Sair de **92% código / 85% usável leigo** → **100% produto que leigo abre e usa sem manual**, interface **melhor que CEOGPT/Mark-LII**, conexões **reais** (navegador + WhatsApp/Telegram + arquivo + web) e **1 programa 7 peças** intacto.
> **Tempo:** 100-110m em 6 fases (pode fatiar F6-1+2 = 50m para MVP leigo)
> **Refs:** Axiom #1-7 + CIPHER 025-035 + 10 Livros + Sites Mark-LII vTIq4pUR7o0 / Mark-XXXIX iq0DlY0Sg-k / CEOGPT moritz.ceogpt.de/jarvis-aufbau glassmorphism HUD pulse hue wheel chime 2.4s styles.css?v=6 / HUD reactor DcjTYTiCt6P
> **Próximo tag:** `v1.5.0-leigo-100`

---

## 0) ONDE ESTAMOS — % HONESTO PÓS-F5 (revalidação 16/16)

| Camada | Código | Usável leigo (abre localhost:8000) | Gap que trava leigo |
|--------|--------|------------------------------------|---------------------|
| P0 Hardening + P6 Data + P7 Integração | 100% | 100% infra | — |
| P6 Obs (Grafana 9 panels by(le) 401/200) | 100% | 95% dev vê painel, leigo não | Leigo não abre :3000 |
| P1 Voz STT small int8 + TTS piper 6 voices + wake Web Speech | 100% | 75% | Wake 1 click escondido em Settings, sem preview, precisa saber de token |
| Chat E2E qwen2.5:0.5b poll 48s | 100% | 70% | `Badge sem token` assusta, precisa ir em Settings > Obter token dev (2 cliques demais) |
| UI 5 telas (Chat/Memory/Approvals/Obs/Settings) | 90% | 65% | Visual shadcn cru, sem glass, sem HUD reactor, sem streaming markdown, sem histórico lateral, sem tour |
| Conexões | 60% | 30% | `browser_control` playwright, `send_message` WhatsApp/Telegram via n8n webhook `http://n8n:5678/webhook`, file drop 500MB, web_search Tavily não expostos no Chat |
| Infra 7/7 `jefrey_*` | 100% | 85% | `start_jefrey.bat` funciona mas sem wizard, 5 volumes órfãos `jarvis_jefrey_*` confundem |
| Docs leigo | 80% | 70% | `GUIA_LEIGO_JEFREY.md` 115→70L após slim, mas sem tour interativo no app |

**Por que “nunca funciona nada” para leigo hoje (3 fios, não lógica):**
1. **Auth 401 correto mas assusta** — Badge `sem token` + erro 401 parece site quebrado (Axiom #1 FAIL-CLOSED ok, falta auto-bootstrap).
2. **Voz escondida** — VoiceButton existe mas wake/voz em Settings, sem feedback “fale já”.
3. **Visual genérico** — sem CEOGPT glass + HUD pulse + chime; parece “dashboard admin”, não “J.A.R.V.I.S.”.

**Vantagem já temos vs Mark-LII/XXXIX:** RBAC+HITL+Audit dual-write+pgvector HNSW 21/21+Prometheus by(le)+n8n wiring+175/175 — eles não têm. Só falta a **casca leigo**.

---

## 1) O QUE FALTA PARA 100% LEIGO — 6 GAPS

| # | Gap | Severidade | Onde mora hoje | O que CEOGPT/Mark tem |
|---|-----|------------|----------------|----------------------|
| G1 | **Onboarding zero-clique** — leigo abre e já conversa, sem saber o que é token | 🔴 ALTA | `Chat.tsx` mostra badge `sem token`, `Settings.tsx` fetchDevToken manual | CEOGPT auto-init + tour 3 steps |
| G2 | **Interface HUD** — reactor central pulse 1.0-1.6 ligado a `AnalyserNode + LLM latency`, glassmorphism, hue wheel, chime 2.4s, markdown streaming | 🔴 ALTA | `index.css` Tailwind puro, `VoiceButton` pulse simples, Chat lista `h-[42vh]` sem glass | Mark-LII CSS `scale 1.0-1.6 neon cyan` + CEOGPT `styles.css?v=6` + HUD DcjTYTiCt6P |
| G3 | **Histórico + streaming** — sidebar threads + resposta token-by-token markdown (não poll 48s seco) | 🟡 MÉDIA | Poll `running→complete 48s` mostra só “Jefrey pensando…”, sem stream, sem lista de threads | CEOGPT stream + Mark sidebar |
| G4 | **Conexões reais 1-clique** — `Navegar`, `Enviar WhatsApp/Telegram`, `Anexar arquivo`, `Buscar web` direto no Chat | 🟡 MÉDIA | Skills existem (`playwright`, `send_message`, `file`, `web_search`) mas só via tool calling LLM, sem botão | Mark-LII `browser_control` + `send_message` via `n8n:5678/webhook` + file 500MB |
| G5 | **PWA + Instalável** — ícone, manifest, offline `vite.svg`, `start_jefrey.bat` 1 duplo-clique com wizard | 🟡 MÉDIA | Sem `manifest.json`, sem `serviceWorker`, bat simples | CEOGPT PWA |
| G6 | **Observabilidade leigo** — Health virou “luz verde/vermelha gigante” + Grafana link escondido, não dashboard cru | 🟢 BAIXA | `HealthBadge` pequeno, `Observability.tsx` mostra link 9 panels cru | CEOGPT HUD status |

---

## 2) ARQUITETURA F6 — 1 PROGRAMA 7 PEÇAS (Axiom #7 sem novo container)

```
jefrey-api:8000  ← reuso para tudo (Chat + STT/TTS + /auth/dev-token + StaticFiles / + /assets/*)
  ├─ novo: POST /onboarding/bootstrap (dev-only, retorna token+thread demo e já seta localStorage via header)
  ├─ existente: /chat + /chat/status (poll 60s keep) — adicionar SSE /chat/stream (opcional, fallback poll)
  ├─ existente: /stt /tts /voices + /health + /metrics + /openapi
  └─ StaticFiles / → src/jefrey/static (Vite 5.4.2 build 5 chunks → 6 chunks pós-HUD)
jefrey-postgres:5432  pgvector HNSW m16 ef64
jefrey-redis:6379     Streams XADD 10000 DLQ 5000 kid v1/v2
jefrey-mcp:8001      MCP stdio + streamable-http (browser_control playwright exposto)
jefrey-n8n:5678      webhooks /webhook/jefrey-send-message (WhatsApp/Telegram) + /webhook/jefrey-browser
jefrey-prometheus:9090  scrape :8000/metrics (cap5 sem user_id, cap6 by(le))
jefrey-grafana:3000   9 panels editable:false orgId:1
volumes jefrey_*      explicit name (prune jarvis_* órfãos só após pg_dump + BGSAVE em F6-4)
```

**Princípio:** Nenhum `docker run` novo. Voz já reusa `jefrey-api` (faster-whisper small int8 352MB host). HUD pulse é `AnalyserNode.getByteFrequencyData()` + `fetch /metrics jefrey_llm_latency_seconds` no front, zero backend novo.

---

## 3) FASES F6 — ORDEM CANÔNICA (SWE cap14 + DDIA cap6 + Axiom #1)

### F6-1 Onboarding Zero-Clique (20m) — **MVP leigo, faz primeiro** — Axiom #1-2, CIPHER-021, Livro 3 cap8, Mark Auto-Start

**Problema:** Leigo vê `sem token` e fecha aba.

**Fazer:**
- `ui/src/lib/api.ts` — `ensureDevToken(): Promise<string>` tenta `POST /auth/dev-token` silencioso em `useEffect` no `App.tsx` se `!getToken()` e `JEFREY_ENV=dev` (fail-closed em prod 403). Guarda em localStorage. Nunca mostra token em URL.
- `ui/src/components/OnboardingWizard.tsx` (novo) — modal 3 passos **só primeira visita** (`localStorage jefrey_onboarded != 1`): 1) “Oi, sou Jefrey — 1 programa 7 peças” 2) “Digite ou fale” com demo `thread demo-1` 3) CTA `Começar →` foca input Chat. Dismiss guarda `1`. Reabrir via `?tour=1` ou Settings.
- `ui/src/pages/Chat.tsx` — remover `Badge sem token` vermelho assustador → `Badge Pronto` verde se `hasToken` (auto). Erro 401 vira CTA “Clique para liberar acesso (1s)” que chama `ensureDevToken()` + retry.
- `ui/src/pages/Settings.tsx` — manter “Obter token dev” mas texto “Já está pronto — este é só avançado”.
- `src/jefrey/api/auth.py` — nada muda (já 403 em prod). Só garantir `POST /auth/dev-token` público em `auth_middleware._PUBLIC_PATHS` (já tem `/auth/dev-token`).

**Toca em:** `ui/src/lib/api.ts`, `ui/src/App.tsx`, `ui/src/components/OnboardingWizard.tsx` (novo), `ui/src/pages/Chat.tsx`, `ui/src/pages/Settings.tsx`, `src/jefrey/api/auth_middleware.py` (verificar)

**DoD F6-1:** Abrir `http://localhost:8000` incógnito → sem badge vermelho, wizard 3 steps → `Enviar “oi”` → 200 running→complete 48s sem ir em Settings. `POST /auth/dev-token` 200 len64 automático. `POST /chat anon 401` ainda FAIL-CLOSED se limpar storage (prova).

**Prova:** `curl POST /auth/dev-token 200` + `live 16/16` sem toque em Settings.

---

### F6-2 UI CEOGPT Glass + HUD Reactor (30m) — **maior salto visual** — Livro 4 cap11 Grafana, CEOGPT `styles.css?v=6` + HUD DcjTYTiCt6P + Mark-LII vTIq4pUR7o0

**Problema:** Parece painel admin shadcn, não J.A.R.V.I.S.

**Fazer:**
- `ui/src/index.css` — tokens CEOGPT: `--glass: rgba(255,255,255,0.06) + backdrop-blur 16px + border 1px rgba(34,211,238,0.2) + shadow neon 0 0 20px rgba(34,211,238,0.3)`. Adicionar `styles.css?v=6` bump via `index.html?v=6` cache bust.
- `ui/src/components/HudReactor.tsx` (novo) — círculo 180px `border 2px cyan-400` + `animate-pulse 2.4s` + `scale 1.0→1.6` ligado a `level` de `useVoice` **e** a `jefrey_llm_latency_seconds` (fetch `/metrics` parse `histogram_quantile`). Mostra `LLM p95 52ms ef64` + `7/7 healthy` verde. Clique = falar.
- `ui/src/components/ThemeWheel.tsx` (novo, P3 leve) — hue wheel 0-360° altera `--hue` CSS var (CEOGPT). Salva `localStorage jefrey_hue`. Botão em Settings + atalho header.
- `ui/src/App.tsx` — header vira glass `sticky backdrop-blur` + HUD no topo + `HealthBadge` gigante verde/vermelho (não texto pequeno).
- `ui/src/lib/audio.ts` + `useVoice` — chime `AudioContext` 2.4s sintetizado (sine 440→880Hz) no primeiro `start()` ou no mount (1x por sessão, guarda `sessionStorage chime=1`).
- `ui/src/pages/Chat.tsx` — bolhas `glass` + markdown `react-markdown` + `code` copy, `h-[52vh]` com blur, input `glass` + VoiceButton ao lado (já tem), loading `HudReactor` pulse em vez de “Jefrey pensando…”.
- `ui/index.html` + `vite.config.ts` — bump `styles.css?v=6` + `manifest` link.

**Toca em:** `ui/src/index.css`, `ui/src/components/HudReactor.tsx`, `ui/src/components/ThemeWheel.tsx`, `ui/src/App.tsx`, `ui/src/pages/Chat.tsx`, `ui/src/components/VoiceButton.tsx` (refine pulse), `ui/index.html`, `ui/src/lib/audio.ts`

**DoD F6-2:** `lighthouse` performance >90, CLS 0, HUD pulsa 1.0-1.6 com voz e com LLM p95, glass visível, chime 1x, markdown renderiza `**bold**` e ` ```code``` `.

**Refs:** CEOGPT `moritz.ceogpt.de/jarvis-aufbau` + Mark-LII `vTIq4pUR7o0` + HUD `DcjTYTiCt6P`.

---

### F6-3 Conexões Reais 1-Clique (25m) — **supera Mark** — MCP Spec 2026-07-28 + n8n + CIPHER-032 + Axiom #4

**Problema:** LLM pode chamar tools, mas leigo não sabe que existe “navegar” ou “mandar zap”.

**Fazer:**
- `ui/src/components/ConnectionHub.tsx` (novo) — 4 botões no Chat: `🌐 Navegar` `📎 Arquivo` `🔍 Buscar` `💬 Enviar` — cada um:
  - `Navegar` → `POST /mcp/browser_control` (via `src/jefrey/mcp/client.py` stdio → playwright) ou fallback `POST http://n8n:5678/webhook/jefrey-browser` `{url, user_id}`. Mostra screenshot/iFrame no Chat.
  - `Enviar` → `POST http://n8n:5678/webhook/jefrey-send-message` `{to, channel: whatsapp|telegram, text, user_id}` — fail-closed sem webhook → toast “Configure n8n webhook em Settings”.
  - `Arquivo` → drop zone `input[type=file]` → `POST /memory/add` + `pg_memory` HNSW + preview. Suporta 500MB chunked (DDIA cap3).
  - `Buscar` → `POST /mcp/web_search` Tavily → card resultados com `source` + `snippet`.
- `ui/src/pages/Settings.tsx` — seção **Conexões** (nova): `N8N_WEBHOOK_URL`, `TAVILY_API_KEY` (opcional), toggle `browser_control` enabled, teste `Testar webhook` 200/401.
- `src/jefrey/api/main.py` — mount `POST /connections/test` (dev-only proxy para n8n health) + CORS explicit já ok.
- `docker/n8n` — nada novo, só `n8n:5678` já healthy. Documentar workflows em `docs/CONEXOES_N8N.md` (novo).
- `src/jefrey/skills/*` — garantir `web_search`, `automation`, `drive`, `email` já registrados 42 tools (verificado P7 54/54). Adicionar `browser_control` se missing em `src/jefrey/skills/automation.py` (playwright `page.goto`).

**Toca em:** `ui/src/components/ConnectionHub.tsx`, `ui/src/pages/Chat.tsx` (slot Hub), `ui/src/pages/Settings.tsx` (conexões), `src/jefrey/skills/automation.py`, `docs/CONEXOES_N8N.md` (novo), `src/jefrey/api/main.py` (opcional proxy)

**DoD F6-3:** Leigo clica `Navegar → https://example.com` → vê título + screenshot no Chat sem digitar prompt. `Enviar → WhatsApp +5511... “ola”` → n8n webhook 200 (ou toast guia). `Anexar PDF` → `memory/search` acha depois. `Buscar “Jefrey”` → card Tavily.

---

### F6-4 PWA + Infra One-Click (15m) — DDIA cap3 Persistence + SWE cap8 Style + Axiom #5

**Problema:** Leigo fecha aba e perde ícone; volumes órfãos confundem; sem backup prova.

**Fazer:**
- `ui/public/manifest.json` (novo) — `name Jefrey`, `display standalone`, `icons 192/512 vite.svg→png`, `theme_color #06b6d4` (cyan). `ui/index.html` link manifest + `theme-color`.
- `ui/src/main.tsx` — registrar `serviceWorker` simples cache `vite.svg + /assets/* + /` (workbox ou manual `navigator.serviceWorker.register('/sw.js')`).
- `ui/public/sw.js` (novo) — cache-first `assets`, network-first `/chat`.
- `scripts/start_jefrey.bat` — v2: `docker compose up -d --build` + `timeout 8` + `start http://localhost:8000` + `echo Jefrey pronto — 7/7 healthy` + `docker compose ps`. Manter `scripts/start_jefrey.ps1` mirror.
- `docker-compose.yml` — já `name: jefrey` + `name: jefrey_*` OK (F0). Não mexer.
- **Volumes órfãos** — procedimento seguro (DDIA cap3): `docker exec jefrey-postgres pg_dump -U jefrey jefrey > reports/p6-backup-$(date).sql` RC0 + `docker exec jefrey-redis redis-cli -a $REDIS BGSAVE` + `docker volume rm jarvis_jefrey_grafana_data jarvis_jefrey_pgdata ...` **só após dump OK** + `docker compose down -v`? Não — só remove `jarvis_*` órfãos, mantém `jefrey_*` 5. Provar `reports/p6-backup.log` novo timestamp.
- Ícones: converter `vite.svg` 100B → `pwa-192.png` + `pwa-512.png` via `sharp` ou fallback svg.

**Toca em:** `ui/public/manifest.json`, `ui/public/sw.js`, `ui/index.html`, `ui/src/main.tsx`, `scripts/start_jefrey.bat`, `reports/p6-backup.log` (regen), `docker-compose.yml` (só se missing manifest)

**DoD F6-4:** Instalar PWA `Chrome > Instalar Jefrey` → ícone cyan. `start_jefrey.bat` duplo-clique → 7/7 + browser abre. `docker volume ls | findstr jarvis` → 0 após backup. `reports/p6-backup.log` timestamp novo.

---

### F6-5 Tour + Guia Leigo + Observabilidade Simplificada (10m) — Pragmatic 20th + Livro 4 cap11

**Fazer:**
- `docs/GUIA_LEIGO_JEFREY.md` — reescrever 1 página **5 passos** com prints: 1) duplo-clique bat 2) abrir `localhost:8000` 3) falar/clicar HUD 4) conectar Zap 5) ver Grafana se quiser. Link no wizard + Settings `Ajuda`.
- `ui/src/components/Tour.tsx` (novo) — `react-joyride` ou manual 4 steps: Chat → Voice → Conexões → Observabilidade. Trigger `?tour=1` ou botão `?` header. Guarda `localStorage tour_done`.
- `ui/src/pages/Observability.tsx` — simplificar: 3 cards grandes `LLM p95 52ms` `7/7 healthy` `42 tools` + link `Abrir Grafana 9 panels` (não embed cru). Grafana permanece `http://localhost:3000` auth `admin/BGl***ALZ` (já 200).
- `README.md` — badge `v1.5.0-leigo-100` + `start_jefrey.bat` + `Guia Leigo` em topo.

**Toca em:** `docs/GUIA_LEIGO_JEFREY.md`, `ui/src/components/Tour.tsx`, `ui/src/pages/Observability.tsx`, `ui/src/App.tsx` (botão ?), `README.md`

**DoD F6-5:** Leigo sem ler docs faz tour 4 steps e entende tudo em 90s. Guia leigo 1 página sem jargão.

---

### F6-6 Gates 2x + Tag v1.5.0-leigo-100 (10m) — SWE cap14 idempotente + Axiom #1

**Gates (rodar 2x na ordem, sem pular):**
```
python scripts/_validate_deep.py          # 175/175 WARN0 BUG0 2x
python scripts/verify_p6_data.py          # 21/21 2x
python scripts/verify_p6.py               # 27/27 9 panels by(le) editable false 2x
python scripts/verify_p7.py               # 54/54 2x
python -m pytest -q                       # 40 passed 2x
python -m compileall -q src               # RC0
docker compose config -q                  # RC0
docker compose ps                         # 7/7 jefrey-* healthy
# live 16/16 (mesmo _f5_live.py mas com F6 wizard)
GET /health 200 + /metrics jefrey_ + /vite.svg 100 + /openapi 7738 + prometheus /-/healthy 200
+ grafana /api/health 200 + anon 401 + auth 200 panels 9 + ollama qwen2.5 + POST /auth/dev-token 200
+ POST /chat Bearer poll 48s + /stt/health + /tts/health + /tts/voices 6 + PWA manifest 200 + /sw.js 200
+ guard_anti_patterns 6/6 + no head/tail (usa python ports)
```

**Git:**
```
git checkout -b feat/f6-leigo-100
git add <todos F6-1..5>
git commit -m "feat(f6): leigo 100 HUD glass + onboarding auto + conexoes n8n + PWA + tour — v1.5.0"
git push origin feat/f6-leigo-100
git tag -a v1.5.0-leigo-100 -m "F6 Leigo 100 APROVADO — 175/175 16/16 + PWA + HUD + conexoes"
git push origin v1.5.0-leigo-100
git checkout main && git merge --no-ff feat/f6-leigo-100 -m "merge(f6): feat/f6-leigo-100 -> main - v1.5.0" && git push origin main
```

**DoD F6-6:** Todos gates verdes 2x + `git status clean` + tag `v1.5.0-leigo-100` local+remote + `main` SYNCED.

---

## 4) BACKLOG P2/P3/P4 — O QUE VIRA F6 vs PÓS-F6

| Backlog | Vira F6? | Por quê |
|---------|----------|---------|
| P2 `browser_control` playwright + `send_message` n8n | **SIM F6-3** | Já tem MCP/n8n, só expor botão leigo |
| P2 `file` 500MB + `web_search` Tavily | **SIM F6-3** | Já existe skill, só drop zone + card |
| P3 Theming hue wheel + glass tokens `styles.css?v=6` | **SIM F6-2** | CEOGPT core visual |
| P3 HUD pulse 1.0-1.6 + chime 2.4s | **SIM F6-2** | 1 linha Analyser + AudioContext |
| P3 PWA standalone | **SIM F6-4** | 3 arquivos |
| P4 QR AES-256-CBC Remote Dashboard + Morning Briefing + Hardware Monitoring + Clipboard Intelligence | **NÃO F6** (vira `v1.6.0-extras`) | Requer BLE/serial + QR crypto + cron briefing — 2h separado, não bloqueia leigo 100% |

**F6 fecha 100% leigo sem P4.** P4 é “delight”, não “funciona”.

---

## 5) RISCOS E TRAVAS (Axiom #1 FAIL-CLOSED)

| Risco | Mitigação |
|-------|-----------|
| Quebrar 175/175 com UI nova | `python -m compileall` + `verify_p7` no pre-commit já travam; Hub é só UI, não toca `signing.py`/`policy.py` |
| Auto dev-token em prod liberar 403 | `auth.py` `is_prod → 403` fail-closed permanece; `App.tsx` só auto se `fetch /auth/dev-token` 200, senão mostra erro humano |
| n8n webhook sem `N8N_BASIC_AUTH` 401 | `ConnectionHub` testa `GET http://n8n:5678/health` antes, toast “Configure n8n em Settings” |
| Volumes órfãos rm sem backup corromper | **Só rm após `pg_dump RC0` + `BGSAVE` OK** + verificar `reports/p6-backup.log` timestamp |
| Poll 48s ainda seco | F6-2 HUD pulse mostra progresso; futuro `/chat/stream` SSE pode vir em `v1.5.1` sem quebrar poll (fallback) |
| PWA quebra `/api` cache | `sw.js` network-first para `/chat`, `/auth`, `/stt`, `/tts`; cache-first só `/assets/*` |

---

## 6) COMANDOS GO F6 (copiar-colar na ordem)

```bash
# F6-0: trava base
git checkout -b feat/f6-leigo-100
python scripts/_validate_deep.py && python scripts/verify_p6_data.py && python scripts/verify_p7.py && echo "F6-0 OK 175/175 54/54"
docker compose ps # 7/7 jefrey-*

# F6-1 onboarding
# editar ui/src/lib/api.ts ensureDevToken + ui/src/components/OnboardingWizard.tsx + Chat.tsx + App.tsx
npm --prefix ui run build # gera src/jefrey/static 6 chunks
docker compose up -d --build jefrey-api && timeout /t 8 && curl http://127.0.0.1:8000/health && curl http://127.0.0.1:8000/vite.svg

# F6-2 HUD
# editar ui/src/index.css glass tokens + HudReactor.tsx + ThemeWheel.tsx + App.tsx + audio chime
npm --prefix ui run build && docker compose up -d --build jefrey-api

# F6-3 conexões
# editar ConnectionHub.tsx + Settings.tsx conexões + docs/CONEXOES_N8N.md
# opcional src/jefrey/skills/automation.py browser_control

# F6-4 PWA + infra
# criar ui/public/manifest.json + ui/public/sw.js + editar ui/index.html + main.tsx + scripts/start_jefrey.bat
# npm run build + docker compose up -d
# curl http://127.0.0.1:8000/manifest.json 200 + curl /sw.js 200

# F6-5 tour + guia
# editar docs/GUIA_LEIGO_JEFREY.md 1 página + ui/src/components/Tour.tsx + Observability.tsx + README.md

# F6-6 gates 2x + tag
python scripts/_validate_deep.py && python scripts/_validate_deep.py # 175/175 2x
python scripts/verify_p6_data.py && python scripts/verify_p6_data.py # 21/21 2x
python scripts/verify_p6.py && python scripts/verify_p6.py # 27/27 2x
python scripts/verify_p7.py && python scripts/verify_p7.py # 54/54 2x
python -m pytest -q && python -m pytest -q # 40 2x
python -m compileall -q src && docker compose config -q && docker compose ps # 7/7
python scripts/_f6_live.py # 18/18 (16 + manifest + sw.js)
git add -A && git commit -m "feat(f6): leigo 100 HUD glass + onboarding auto + conexoes n8n + PWA + tour"
git push origin feat/f6-leigo-100 && git tag -a v1.5.0-leigo-100 -m "F6 Leigo 100 APROVADO" && git push origin v1.5.0-leigo-100
git checkout main && git merge --no-ff feat/f6-leigo-100 -m "merge(f6): feat/f6-leigo-100 -> main - v1.5.0" && git push origin main
```

---

## 7) PROVA FINAL F6 — O QUE LEIGO VÊ

1. Duplo-clique `scripts/start_jefrey.bat` → `Jefrey pronto — 7/7 healthy — abrindo http://localhost:8000`
2. Browser abre `localhost:8000` → modal “Oi, sou Jefrey — 3 passos” → `Começar` → HUD reactor ciano pulsa + chime suave
3. Digita “oi” ou clica HUD → `Jefrey pensando…` com pulse → resposta markdown 48s + voz opcional `🔊`
4. Clica `🌐 Navegar → google.com` → vê resultado no Chat
5. Clica `📎` arrasta PDF → “Memória salva” → `Memória > Buscar` acha
6. `💬 Enviar → WhatsApp` → n8n 200 ou toast guia (sem quebrar)
7. Instala PWA → ícone cyan na área de trabalho
8. `Observabilidade` → 3 cards gigantes verdes + botão `Abrir Grafana`
9. Fecha e abre de novo → já logado (token guardado), sem wizard

**Métrica “melhor que CEOGPT/Mark”:** 
- CEOGPT tem glass mas não tem RBAC/HITL/pgvector/n8n; Mark tem hardware mas não tem PWA/tour/auto-token. F6 Jefrey junta **glass+HUD+auto+PWA+conexões+n8n+175/175** — comercial 100%.

---

## 8) ESTIMATIVA HONESTA

| Fase | Tempo | Entrega shippable |
|------|-------|-------------------|
| F6-1 onboarding | 20m | Leigo já conversa sem Settings |
| F6-2 HUD glass | 30m | Interface vira “J.A.R.V.I.S.” |
| F6-3 conexões | 25m | Supera Mark em 1-clique |
| F6-4 PWA+infra | 15m | Instalável + bat 1-clique + volumes limpos |
| F6-5 tour+guia | 10m | Zero manual |
| F6-6 gates+tag | 10m | `v1.5.0-leigo-100` selado |
| **Total** | **110m** | **100% leigo funcional** |

**MVP 50m:** F6-1 (20m) + F6-2 sem ThemeWheel (20m) + F6-6 (10m) já entrega 90% leigo. F6-3/4/5 podem ir em `v1.5.1`.

---

## 9) GO / NO-GO

- **GO F6-1 agora?** `git checkout -b feat/f6-leigo-100` + `ensureDevToken` + `OnboardingWizard` → `npm run build` → live 16/16 sem badge vermelho. **Risco baixo, valor alto.**
- **NO-GO:** Nada — base `v1.4.0-final-100` 175/175 16/16 estável, F6 só adiciona UI/UX, não toca `signing/policy/pg_memory` críticos.

> **Aguardando seu “GO F6” para codar.** Diga `GO F6 completo` (110m) ou `GO F6-1 MVP` (50m) que travo `feat/f6-leigo-100` e entrego fase a fase com `16/16→18/18 live` a cada passo.
