# PLANO P1 — VOZ VIVA (STT + TTS + WAKE + HUD) — JEFREY 100% COMERCIAL — 2026-09-03 22:47
# Base: main 72b0107 SYNCED origin/main + v1.2.0-ui — 175/175 2x 21/21 2x 27/27 2x 54/54 2x 40 passed 7/7 healthy

> **Padrão que queremos atingir:** Mark-LII (Voz viva nativa, Theming live hue-wheel, HUD reativo pulse real, Boot chime 2.4s, Plugin System drop-in, 20 actions) + Mark-XXXIX-OR (file 500MB, Adaptive UI, OpenRouter free-tier) + CEOGPT Jarvis Aufbau (moritz.ceogpt.de/jarvis-aufbau — voz + automações + dashboard + estilo comercial) + Reels @Fatima/Julio (estética premium escura vidro+neon). **Jefrey vence em:** isolamento multi-tenant, HMAC kid rotation, HNSW 768, gates 175/175, HITL DLQ, 7/7 healthy, Prometheus cardinality <800 — eles NÃO têm isso. Vamos trazer o que eles têm (voz/HUD/tema) SEM quebrar o que já é 100%.

---

## 0) Estado P0 (não quebrar — Axiom #1 FAIL-CLOSED)

| Gate | 22:15 f6381e2 | 72b0107 |
|------|---------------|---------|
| deep 175/175 2x | ✅ WARN0 BUG0 | re-provar 2x antes codar P1 |
| verify_p6_data 21/21 2x | ✅ 100% DATA OK | re-provar |
| verify_p6 27/27 2x | ✅ 8 panels editable false by(le) | re-provar |
| verify_p7 54/54 2x | ✅ mock rate+hitl | re-provar |
| pytest 40+6=46 | ✅ 40 passed | re-provar |
| compileall -q | ✅ OK | re-provar |
| docker 7/7 healthy | ✅ postgres/redis/api/mcp/n8n/prom/grafana | re-provar |
| live /health /chat /memory | ✅ / 200 5 chunks, /chat 401→200 running, /memory/search 200 | re-provar |
| ollama 2/2 | nomic 274MB 200 OK + llama3.1:8b OOM 3.3GB alloc (infra RAM, não bug) | workaround P1.0 |

- UI 5 chunks 632.7kB (vendor163 + charts383 + query38 + ui21 + index26) 891 modules — code-split OK (fix vite.config.js stale).
- docker-compose: JEFREY_LLM__BASE_URL + JEFREY_EMBEDDINGS__BASE_URL = host.docker.internal:11434 + extra_hosts host-gateway (71 + 129) — prova: docker exec env == host.docker.internal.
- `.env` localhost comentado; compose explicit postgres:5432 redis:6379 sem fallback.

---

## 1) Diretrizes que governam P1 (obrigatório citar em cada commit/PR)

### Axiom #1-7 — 6 PRINCÍPIOS FAIL-CLOSED
| Axiom | Regra | Como P1 obedece |
|-------|-------|-----------------|
| #1 FAIL-CLOSED deny/false/raise | Toda falha nega | /stt sem token → 401; whisper fail → 500 fail-closed não fake transcript; TTS fail → fallback texto sem inventar áudio |
| #2 ISOLAMENTO user_id=None guest | guest não vê dado alheio | /stt, /tts, /wake exigem user_id; XADD topic jefrey.events.{user_id}.stt |
| #3 SEM STUB EM PROD | JEFREY_ENV dev/prod | whisper mock só se JEFREY_ENV=dev e JEFREY_STT__MOCK=true; prod validate_for_production() bloqueia |
| #4 PERSISTÊNCIA REAL | Redis setex pipeline incr/expire TTLCache só dev | rate limit /stt pipeline fail-closed; DLQ jefrey:dlq:{user_id} maxlen5000 |
| #5 CRIPTO urlsafe_b64 sem padding RS256+kid aud/iss/exp/kid/alg compare_digest sort_keys kid v1→v2 | HMAC STT kid rotation idem EventBus | HMAC user_id.timestamp.canonical_transcript |
| #6 LEAST PRIVILEGE overwrite=False :ro CORS explicit allow_credentials False pool_pre_ping 3600 | /stt CORS enumerated, StaticFiles mount sem expor /api |
| #7 1 programa 7 peças → 8 peças? NÃO | Sem novo container | STT/TTS dentro de jefrey-api (python) + UI MediaRecorder; não criar jefrey-stt container |

### CIPHER 025-035
- **032 Skill Risk** — stt/tts = RiskLevel MEDIUM (HITL? não — auto-allow user, mas HIGH/C RITICAL deny). Registrar em ToolRegistry.
- **033 HMAC-SHA256 EventBus kid v1/v2 dual-verify** — cada stt event XADD com hmac + kid; consumer XREADGROUP verify dual.
- **026 Rate limiting pipeline fail-closed** — /stt 10 req/min por user_id via Redis incr/expire pipeline; falha redis → deny.
- **031 OAuth2 JWKS/introspect** — /stt valida Bearer idem /chat (TTLCache 1024/60 hash(token)).
- **035 Token Refresh** — TTS ElevenLabs api key rotacionável via JEFREY_TTS__API_KEY + kid.
- **028/029 Policy** — PolicyEngine decide stt/tts antes de executar.
- **021 silent except** — proibido except: pass em stt; logar DLQ.
- **010 audit** — audit log stt request/response.
- **025 dual-write** — se transcrever, persiste em memory + retorna ao chat.

### 10 Livros — REFERENCES_MAPPING.md
1. **MCP Spec 2026-07-28** — /stt como Tool MCP (input audio b64, output transcript) + streaming?
2. **OpenAI Agents Cookbook** — Agent orquestra stt→memory→llm→tts (turno voz).
3. **Security Engineering (Ross Anderson 3rd)** — cap voz spoofing, replay attack → HMAC timestamp janela 5min.
4. **Prometheus Up & Running 2nd** — cap5 cardinality (<800), cap6 histogram stt_duration_seconds, cap10 alert JefreySttLatencyHigh, cap11 Grafana panel 9º.
5. **DDIA (Kleppmann)** — cap3 persistência transcript, cap5 replication, cap6 partitioning por user_id, cap12 tuning HNSW já OK.
6. **SWE at Google** — cap8 style (typing, docstring), cap14 testing (pytest stt 6 novos = 46→52).
7. **Fluent Python 19-21** — async, context manager para audio stream.
8. **High Performance Python cap1-4** — cProfile stt, orjson, lru_cache, memory_profiler; bench p50/p95 stt <800ms.
9. **Building LLM Applications O'Reilly 2024** — fallback Ollama OOM → texto sem voz (não quebrar).
10. **Pragmatic Programmer 20th** — DRY lib/api.ts, ortogonalidade stt vs chat.

### Sites — inspiração estética/funcional
- **CEOGPT Jarvis Aufbau (moritz.ceogpt.de/jarvis-aufbau/)** — dashboard escuro vidro, automações, voz natural, wake word, cópia tokens styles.css?v=6.
- **Julio @onigashima reels** — HUD reator pulse, neon ciano/magenta, glassmorphism.
- **FatihMakes Mark-LII (github.com/FatihMakes/Mark-LII.git — 100k main.py 171k ui.py, 20 actions, PyQt6 HUD, Gemini native audio 16k/24k, 5 vozes Charon/Puck/Kore/Fenrir/Aoede, hue wheel, pulse, chime 2.4s, PluginRegistry _NAME_RE ^[a-z_][a-z0-9_]{0,63}$)**
- **Mark-XXXIX-OR (40598 main.py 57745 ui.py, file 500MB, Adaptive UI, OpenRouter free-tier, 40% faster)**
- **YouTube vTIq4pUR7o0 / iq0DlY0Sg-k / x5ZIzhOqTzE + reel DcjTYTiCt6P** — demo voz viva, latência <1s, barge-in.

---

## 2) Gap Jefrey vs Eles (o que falta trazer)

| Feature | Mark-LII/XXXIX | CEOGPT | Jefrey hoje | P1 vai fazer |
|---------|----------------|--------|-------------|--------------|
| STT vivo | Gemini native audio 16k | Whisper mistral | ❌ só texto | ✅ Whisper.cpp faster-whisper + MediaRecorder |
| TTS vivo | Gemini 5 vozes | ElevenLabs | ❌ | ✅ ElevenLabs + fallback pyttsx3 |
| Wake word | porcupine "jarvis" | "hey jarvis" | ❌ | ✅ porcupine/pvporcupine 1.9 |
| HUD pulse real | audio level → scale | reator | ❌ static | ✅ Web Audio Analyser → CSS scale |
| Theming hue wheel | Live Theming | dark glass | ❌ Tailwind fixo | P3 (não P1) |
| Chime boot 2.4s | synthesized | — | ❌ | P3 |
| Plugins drop .py | PluginRegistry collision | — | ❌ | P2 |
| File 500MB | Advanced File Handling | — | ❌ 10MB | P2 |
| 20 actions | 20 tools | — | 8 tools | P2 (+12) |

**P1 foca SÓ voz — não thema, não plugin, não file500MB (ordem B preserva 175/175).**

---

## 3) Arquitetura P1 Voz (sem novo container — Axiom #7)

```
[UI Chat] --MediaRecorder opus/webm 16k--> POST /stt (Bearer+user_id+rate+HMAC) --> faster-whisper (pt-BR) --> transcript
   |-> POST /chat {transcript} --> Ollama llama3.1:8b (ou 3b workaround) --> resposta texto
   |-> POST /tts {texto} --> ElevenLabs (ou pyttsx3 fallback) --> audio/mpeg --> <audio autoplay>
   |-> HUD pulse: AnalyserNode.getByteFrequencyData() --> --pulse:scale
[Wake] porcupine wasm "jarvis" --> start Recording
```

- **Backend:** `src/jefrey/api/stt.py` + `src/jefrey/api/tts.py` + `src/jefrey/core/stt_engine.py` (faster-whisper) + `src/jefrey/core/tts_engine.py` (elevenlabs).
- **Frontend:** `ui/src/components/VoiceButton.tsx` + `ui/src/hooks/useVoice.ts` + `ui/src/lib/audio.ts` (MediaRecorder + Analyser).
- **Config:** `src/jefrey/core/config.py` add STTSettings/TTSSettings (model, lang, api_key, mock).
- **Metrics:** `src/jefrey/core/metrics.py` histogram stt_duration_seconds + tts_duration.

---

## 4) Plano P1 — 6 passos (60m) — ORDEM IDEAL

### P1.0 Infra RAM workaround (5m) — antes de codar voz
- **Por quê:** llama3.1:8b OOM 3.3GB alloc fail (prova viva /api/chat 500) bloqueia demo voz→llm. Não é bug código (Axiom #1 fail-closed correto).
- **Fazer:** `ollama pull llama3.1:3b` (2.0GB) OU `qwen2:0.5b` (0.5GB) + `JEFREY_LLM__MODEL=llama3.1:3b` em .env + compose + `warmup_model() keep_alive -1 num_gpu 99` já OK.
- **Prova:** `curl http://localhost:11434/api/generate -d '{"model":"llama3.1:3b","prompt":"hi"}' ` 200 <1s após warmup.
- **DoD:** /chat 200 com texto real (não "Execução longa iniciada..." apenas).

### P1.1 STT Engine (15m) — faster-whisper
- **Arquivo:** `src/jefrey/core/stt_engine.py` (~120L)
  - `class STTEngine: model = WhisperModel("small", device="cpu", compute_type="int8")` (pt-BR, 244MB) — lazy load, lru_cache.
  - `transcribe(wav_bytes: bytes) -> str` — tempfile opus→wav 16k via ffmpeg (fallback pydub), cProfile cap1 bench.
  - Mock: se JEFREY_ENV=dev e JEFREY_STT__MOCK=true → retorna "mock transcript".
- **Livro8 HPP:** orjson + memory_profiler, bench 10 áudios p50 <600ms p95 <900ms.
- **Gate:** `pytest tests/test_stt_engine.py` 3 tests + `compileall -q`.

### P1.2 API /stt + /tts (15m) — FastAPI + Policy + HMAC + Rate
- **Arquivo:** `src/jefrey/api/stt.py` + `tts.py` (~180L cada)
  - `POST /stt` — multipart audio/webm, Bearer + PolicyEngine (Risk MEDIUM), rate 10/min pipeline, HMAC kid v1/v2, XADD jefrey.events.{user_id}.stt, DLQ, Prometheus histogram.
  - `POST /tts` — JSON {text, voice_id}, ElevenLabs client + fallback pyttsx3, rate 20/min.
  - Registrar em `src/jefrey/core/tools.py` ToolRegistry risk MEDIUM.
  - `src/jefrey/core/config.py` add STTSettings/TTSSettings.
  - `src/jefrey/api/main.py` include_router(stt_router) + tts_router antes de StaticFiles.
- **Axiom/CIPHER:** fail-closed, isolamento, HMAC, least privilege.
- **Gate:** `pytest tests/test_stt_api.py` 4 tests (401 sem token, 429 rate, 200 mock, HMAC).

### P1.3 Frontend VoiceButton + useVoice (15m) — MediaRecorder + HUD pulse
- **Arquivos:** `ui/src/components/VoiceButton.tsx` (~120L) + `ui/src/hooks/useVoice.ts` (~140L) + `ui/src/lib/audio.ts` (~80L)
  - `VoiceButton` — botão mic (lucide-react Mic), estado idle/recording/processing, AnalyserNode → CSS `--pulse`, borda neon ciano pulse real (CEOGPT/Julio).
  - `useVoice` — MediaRecorder opus 16k, POST /stt com Bearer+user_id, recebe transcript → POST /chat → POST /tts → play audio, error mapHttpError.
  - Integrar em `ui/src/pages/Chat.tsx` — slot ao lado do input.
- **Livro9 Building LLM Apps:** streaming transcript parcial (opcional P1.3b).
- **Gate:** `npm run build` 891 modules → 6 chunks (vendor+charts+query+ui+index+voice ~15kB) + `vite build` OK.

### P1.4 Wake word (5m) — porcupine wasm
- **Arquivo:** `ui/src/hooks/useWakeWord.ts` (~90L)
  - `@picovoice/porcupine-web` 1.9 — keyword "jarvis" (builtin) + VAD, callback → start recording.
  - Toggle Settings → Voice → Wake ON/OFF (persist localStorage).
  - Sem backend — 100% browser (Axiom #7).
- **Gate:** manual — falar "jarvis" → mic auto liga (indicator).

### P1.5 Observabilidade + Gates finais (5m) — Prometheus/Grafana
- **Arquivo:** `src/jefrey/core/metrics.py` add `stt_duration_seconds histogram + tts_duration + stt_requests_total counter`.
- **Arquivo:** `docker/prometheus/prometheus.yml` já OK; `docker/grafana/dashboards/jefrey.json` add panel 9 "STT Latency p95" `histogram_quantile(0.95, sum(rate(stt_duration_seconds_bucket[5m])) by (le))`.
- **Re-provar 2x:** deep 175→183/183 (+8 stt/tts checks) 2x + verify 21→21 2x + verify_p6 27→27 2x (9 panels) + verify_p7 54→54 2x + compileall + pytest 40→52 + guard 6/6 + docker 7/7 + live /stt 401→200 + /tts 200 + vite.svg 200.

---

## 5) O que codar / consertar / construir — checklist minucioso

### CODAR (novos arquivos)
- [ ] `src/jefrey/core/stt_engine.py` — faster-whisper small int8, transcribe(), mock branch, lru_cache 1, WeakValueDictionary cache
- [ ] `src/jefrey/core/tts_engine.py` — elevenlabs==1.12 + pyttsx3 fallback, synthesize(text, voice_id) -> bytes
- [ ] `src/jefrey/api/stt.py` — POST /stt, GET /stt/health
- [ ] `src/jefrey/api/tts.py` — POST /tts, GET /tts/health, GET /tts/voices
- [ ] `ui/src/components/VoiceButton.tsx` — mic + pulse + estados
- [ ] `ui/src/hooks/useVoice.ts` — MediaRecorder + fetch /stt + /chat + /tts
- [ ] `ui/src/hooks/useWakeWord.ts` — porcupine
- [ ] `ui/src/lib/audio.ts` — wav utils, analyser, opus→wav
- [ ] `tests/test_stt_engine.py` (3) + `tests/test_stt_api.py` (4) + `tests/test_tts_api.py` (3) = +10 tests (40→50, + evals 6 = 56)

### CONSERTAR (existentes)
- [ ] `src/jefrey/core/config.py` — add STTSettings( model="small", lang="pt", mock=False) + TTSSettings( provider="elevenlabs", api_key, voice_id="Charon", fallback="pyttsx3")
- [ ] `src/jefrey/api/main.py` — include_router stt/tts antes de StaticFiles mount
- [ ] `src/jefrey/core/tools.py` — registrar stt/tts no ToolRegistry Risk MEDIUM
- [ ] `src/jefrey/core/metrics.py` — histogram stt/tts
- [ ] `docker/grafana/dashboards/jefrey.json` — panel 9 STT Latency (editable false keep)
- [ ] `.env.example` — documentar JEFREY_STT__MODEL + JEFREY_TTS__API_KEY + JEFREY_LLM__MODEL workaround
- [ ] `ui/src/pages/Chat.tsx` — slot VoiceButton
- [ ] `ui/src/pages/Settings.tsx` — toggle Wake + selector voz (5 vozes Mark-LII: Charon/Puck/Kore/Fenrir/Aoede)

### CONSTRUIR (infra)
- [ ] `pip install faster-whisper==1.1.1 elevenlabs==1.12 pyttsx3==2.90 pvporcupine==3.0.3` (ou faster-whisper-cpu) — sem novo container
- [ ] `npm i @picovoice/porcupine-web` — wake word wasm
- [ ] `ollama pull llama3.1:3b` workaround OOM (ou manter 8b se host 8GB+)
- [ ] `ffmpeg` já no host? verificar `ffmpeg -version` — necessário para opus→wav

---

## 6) Comandos copiar-colar (ordem ideal — executar em branch feat/p1-voz)

```bash
# 0) branch + validar P0 2x antes de codar (Axiom #1, SWE cap14)
git checkout -b feat/p1-voz
python scripts/_validate_deep.py && python scripts/_validate_deep.py  # 175/175 2x
python scripts/verify_p6_data.py && python scripts/verify_p6_data.py  # 21/21 2x
python scripts/verify_p6.py && python scripts/verify_p6.py            # 27/27 2x
python scripts/verify_p7.py && python scripts/verify_p7.py            # 54/54 2x
python -m compileall -q src && echo compileall OK
pytest -q  # 40 passed
docker compose ps  # 7/7 healthy
curl -s http://localhost:8000/health | findstr healthy
curl -s http://localhost:8000/metrics | findstr stt

# P1.0 RAM workaround
ollama list
ollama pull llama3.1:3b
# .env: JEFREY_LLM__MODEL=llama3.1:3b
docker compose up -d --wait && docker compose ps

# P1.1-1.2 backend
pip install faster-whisper elevenlabs pyttsx3
# editar src/jefrey/core/config.py, stt_engine.py, tts_engine.py, api/stt.py, api/tts.py, api/main.py, core/tools.py, core/metrics.py
python -m compileall -q src && pytest -q  # 50 passed
curl -H "Authorization: Bearer $JEFREY_API__SECRET_KEY" -F audio=@test.webm http://localhost:8000/stt  # 200 transcript

# P1.3-1.4 frontend
cd ui && npm i @picovoice/porcupine-web && npm run build && cd ..
# editar VoiceButton.tsx, useVoice.ts, useWakeWord.ts, Chat.tsx, Settings.tsx
curl -s http://localhost:8000/ | findstr VoiceButton  # chunk voice presente
docker compose up -d --build --wait

# P1.5 gates finais 2x
python scripts/_validate_deep.py && python scripts/_validate_deep.py  # 183/183 2x
python scripts/verify_p6.py && python scripts/verify_p6.py            # 27/27 9 panels
pytest -q  # 50 passed
docker compose ps  # 7/7
```

---

## 7) DoD P1 — Definition of Done (só mergea se tudo ✅)

- [ ] deep 183/183 2x WARN0 BUG0 (175 + 8 novos stt/tts)
- [ ] verify_p6_data 21/21 2x + verify_p6 27/27 2x (9 panels) + verify_p7 54/54 2x
- [ ] pytest 50 passed (+ evals 6 = 56) + compileall -q + guard 6/6
- [ ] docker 7/7 healthy + compose config -q RC0
- [ ] live: /stt 401 sem token → 200 com token (transcript) + /tts 200 audio/mpeg + /chat voz→texto→llm→voz <2s p95 (nomic 200 + llama 3b 200)
- [ ] UI: Chat mic pulse real + wake "jarvis" + Settings voz selector 5 vozes + build 6 chunks gzip ~190kB
- [ ] Prometheus: stt_duration_seconds histogram + Grafana panel 9 + alert JefreySttLatencyHigh
- [ ] CHANGELOG [1.3.0-p1-voz] + TODO.md sync + tag v1.3.0-p1-voz + git push --tags + merge --no-ff feat/p1-voz → main

---

## 8) Riscos & mitigações

| Risco | Mitigação |
|-------|-----------|
| OOM llama 3.3GB (P0) | P1.0 pull 3b 2GB; se host 16GB pode manter 8b; warmup keep_alive -1 |
| faster-whisper 244MB cold start 5s | lazy load + lru_cache + warmup no startup (transcribe silence) |
| ElevenLabs custo/latência | fallback pyttsx3 local; JEFREY_TTS__PROVIDER=local em dev |
| opus/webm codec browser | MediaRecorder isTypeSupported check + fallback audio/wav |
| porcupine licença | free tier 3 keywords; alternativa: web-speech-api interim |
| CORS mic permission | UI pede getUserMedia, fail-closed sem mic → texto puro continua |

---

## 9) Depois de P1 — P2 Mão + P3 Estética (não codar agora)

- **P2 Mão (60m):** Plugins drop .py PluginRegistry + 20 actions (file 500MB, web_search Tavily, send_message n8n WhatsApp, browser_control playwright, undo/confirm).
- **P3 Estética CEOGPT (45m):** Live Theming hue wheel + Voice Picker 5 vozes + HUD reator + Boot chime 2.4s + npm audit fix (vite 8, react-router 7.18 breaking) — por último para não invalidar 6 chunks.

---

## 10) Referências cruzadas (onde cada diretriz aparece no código P1)

- Axiom #1: `src/jefrey/api/stt.py:401 if no token, 500 transcribe fail, deny` + `stt_engine.py:raise on model load fail`
- CIPHER-033: `stt.py:XADD hmac kid v1/v2 + verify dual`
- Livro4 cap6: `metrics.py:Histogram stt_duration_seconds buckets [0.1,0.3,0.6,1,2]`
- Livro8 cap1: `stt_engine.py:cProfile -o reports/p1-stt.prof`
- Site CEOGPT: `ui/src/components/VoiceButton.tsx:glassmorphism + neon pulse`
- Mark-LII: `Settings.tsx:voiceIds=["Charon","Puck","Kore","Fenrir","Aoede"]`

---

**Próximo comando para executar P1:** `git checkout -b feat/p1-voz` + P1.0 workaround llama3.1:3b — aguardando seu GO para codar.
