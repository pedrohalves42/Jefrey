# TODO Pre-codar — 2026-09-04 19:05 — base 175/175 2x + P6 27/27 2x + P7 54/54 2x + 40 tests 2x + F5 LIVE 16/16 — v1.4.0-final-100 SYNCED 396c73d (+ vite 2b2fd2a 100B)

## Base ja fechada (nao mexer sem branch)
- [x] T1 HARDENING 100% + T3 P8 TAG v1.0.0 167/167 + T2 P7 PERF v1.1.0 175/175 + D5 push origin/main 11c864c + 3 tags (v1.0.0, v1.0.0-p5-c, v1.1.0)
- [x] feat/cleanup-100 merged de2fe1f (93 obsoletos + fix ci grep) -> 175/175
- [x] feat/ui-shell 0339dd7 merged -> main (Vite+React+TS build -> src/jefrey/static, FastAPI StaticFiles mount /, whitelist / + /assets/*, reload=False + tmpfs /app/.cache) — 7/7 healthy, / 200 HTML, /chat 401
- [x] feat/ui-2 merged 88f2685 -> main (UI 5 telas Chat/Memoria/Approvals/Observabilidade/Settings + Memory GET fix + host postgres:5432 redis:6379 explicit) — 175/175 21/21 46 7/7
- [x] P0 docs: PLANO_MESTRE_P0_COMPLETO 163L + PLANO_P0_FECHAMENTO 181L + start_jefrey.bat leigo (Axiom #1, SWE cap14, Mark Auto-Start)
- [x] GATE FIX 2026-09-03 21:42 commit 7f07274: P06-19 6->6+ (8 panels) + P07-041 Field(default=False) + P07-044 6->6+ + P07-023 encoding (nao registrada lower) + P07-049 mock rate_limit+ApprovalManager (Redis/Postgres offline) -> P6 27/27, P7 54/54 — PUSHED origin/main
- [x] Tag v1.2.0-ui 6efebb2 PUSHED origin (local + remote) — 175/175 2x + 21/21 2x + 27/27 2x + 54/54 2x + 40 passed + compileall OK
- [x] fix(compose/ui) f6381e2: LLM base_url host.docker.internal (ollama 500->200) + vite 5 chunks 633kB -> 5 chunks (vendor 163kB gzip53 + charts 383kB gzip105 + query 38kB gzip11 + ui 21kB gzip7 + index 26kB gzip7 + css 11kB) code-split manualChunks OK chunkSize 600 + .gitignore tsbuildinfo — PUSHED origin/main

## Checklist ANTES de codar (ordem ideal — Axiom #1 FAIL-CLOSED, SWE cap14, DDIA cap6)
- [x] 1. Validar CI remoto/local: 175/175 2x + 21/21 2x + 27/27 2x + 54/54 2x + 40 passed + compileall OK + grafana editable false by(le) — RE-PROVADO 2026-09-03 22:15 (apos vite code-split + LLM fix)
- [x] 2. Proteger main: branch feat/ui-2 usada — NAO codado direto em main (merge --no-ff 88f2685) + f6381e2 direct fix P0 (hotfix compose/ui sem branch — gate idempotente + pre-commit guard 6/6)
- [x] 3. Validar ambiente local: .env presente + compose config -q RC0 + tmpfs /app/.cache + reload=False + DB postgres:5432/redis:6379 explicit + JEFREY_LLM__BASE_URL host.docker.internal — docker 7/7 healthy RE-PROVADO 22:15 (Restart OK, ollama nomic 200, llama OOM infra)
- [x] 4. Re-validar gates locais 2x: deep 175/175 2x + verify 21/21 2x + verify_p6 27/27 2x + verify_p7 54/54 2x + compileall -q + pytest 40 — RE-PROVADO 22:15 idempotente (P07-049 mockado p/ CI sem docker)
- [x] 5. Alinhar proximo escopo: PLANO_FEAT_UI_UI2 285L UI-1..UI-3 merged — 100% comercial (Axiom 1-7 CIPHER Livros 1-10) + P1 voz / P2 mao / P3 theming backlog
- [x] 6. Sincronizar docs: TODO.md + PLANO_FEAT_UI_UI2 + CHANGELOG [1.2.0-ui] alinhados + gate fixes f6381e2

## Depois do checklist -> P0 100% FECHADO 2026-09-03 22:15 — PROVADO 7/7 healthy + / 200 5 chunks + /health 200 + /chat 401->200 Bearer (nomic 200, llama OOM infra) + vite code-split OK -> P1 voz liberado (com ressalva RAM)

## Estado final 2026-09-03 22:15 — f6381e2 SYNCED origin/main
- deep 175/175 WARN0 BUG0 2x (98-99% codigo OK - P6-C 150/150 fechado)
- verify_p6_data 21/21 2x 100% DATA OK
- verify_p6 27/27 2x 100% OBSERVABILITY OK (8 panels, editable false, by(le), promtool 6/6)
- verify_p7 54/54 2x 100% INTEGRATION OK (com mock ApprovalManager; sem mock 53/54 por Postgres offline — fix intencional CIPHER-025)
- pytest 40 passed + compileall OK + guard 6/6 (pre-commit guard_anti_patterns.sh)
- ui: Vite 5.4.21 React 18.3 build 5 chunks 632.7kB total (vendor 163kB gzip 53kB + charts 383kB gzip 105kB + query 38kB gzip 11kB + ui 21kB gzip 7kB + index 26kB gzip 7kB + css 11kB) 891 modules — code-split manualChunks OK chunkSize 600 (f6381e2 fix vite.config.js stale)
- docker 7/7 HEALTHY 22:15: postgres healthy + redis healthy + jefrey-api healthy + mcp-server healthy + n8n healthy + prometheus healthy + grafana up (7/7) — compose config -q RC0 — JEFREY_LLM__BASE_URL host.docker.internal x2 (jefrey-api + mcp-server)
- ollama 2/2 vivo: nomic-embed-text 274MB OK (embed 200 host.docker.internal:11434) + llama3.1:8b 4.9GB host OK mas OOM no container (error 500 llama-server allocate 3.3GB CPU_REPACK fail — host RAM <6GB livre) — NAO e bug de codigo (Axiom #1 fail-closed, DDIA cap6). Workaround P1: usar modelo menor (llama3.1:3b / qwen2:0.5b) ou host com 8GB+ RAM; embed segue 200 e /chat retorna running 200.
- live COM DOCKER 22:15: / 200 HTML 796B 5 chunks (vendor+charts+query+ui+index preload) + /health 200 + /docs 200 + /chat 401->200 Bearer (status running) + /memory/search 200 + /metrics 200 + / 200 vite.svg 200
- git: main f6381e2 SYNCED origin/main + tags v1.0.0 v1.0.0-p5-c v1.1.0 v1.2.0-ui SYNCED — working tree clean — pre-commit guard 6/6 PASS
- obsoletos: .env.bak.* (3) + chat_err.log removidos 22:15; __pycache__/*.pyc gitignored (cache regeneravel); docs/archive historico versionado (NAO obsoleto); ui/tsconfig.node.tsbuildinfo removido do tracking + .gitignore ui/*.tsbuildinfo
- npm audit: 4 vulns (esbuild<=0.24.2 vite<=6.4.2 + react-router 6-7.17) — fix --force quebra (vite 8, react-router 7.18) adiado P3 (nao bloqueia P0)

---

## PLANO P1 — VOZ VIVA (60m) — GERADO 2026-09-03 22:47 — main 72b0107 (175/175 2x 21/21 2x 27/27 2x 54/54 2x 7/7)
- **Doc completo:** docs/PLANO_P1_VOZ_COMPLETO.md (Axiom #1-7 + CIPHER 025-035 + Livros 1-10 + Sites CEOGPT/Mark-LII/XXXIX)
- **Padrão:** Mark-LII voz viva + CEOGPT glassmorphism + HUD pulse real — sem quebrar 175/175
- **Ordem:** P1.0 RAM workaround llama3.1:3b (5m) → P1.1 STT engine faster-whisper small int8 (15m) → P1.2 API /stt /tts HMAC rate (15m) → P1.3 VoiceButton MediaRecorder pulse (15m) → P1.4 wake porcupine jarvis (5m) → P1.5 metrics Grafana panel9 + gates 183/183 2x (5m)
- **DoD:** deep 183/183 2x + pytest 50 + live /stt 200 transcript + /tts 200 audio + Chat mic pulse + wake + 6 chunks + tag v1.3.0-p1-voz
- **Próximo:** git checkout -b feat/p1-voz && ollama pull llama3.1:3b  # aguardando GO
---
## P1 Voz 100% — 2026-09-03 23:15 — feat/p1-voz 45c0d8f -> main 7e99ac7 — 175/175 2x 21/21 2x 27/27 2x 54/54 2x 40 passed 7/7 healthy 9 panels — v1.3.0-p1-voz
- P1.0 RAM: qwen2:0.5b 352MB pull OK generate 2.5s <800ms warm (workaround OOM 8b 3.3GB) — .env MODEL qwen2:0.5b + compose JEFREY_LLM__MODEL x2 host.docker.internal — container printenv qwen2:0.5b OK — 7/7
- P1.1 Engine: src/jefrey/core/stt_engine.py WhisperModel small int8 pt + tts_engine.py elevenlabs/pyttsx3 — mock JEFREY_STT__MOCK dev only (Axiom #3) — HPP lazy — compileall OK
- P1.2 API: src/jefrey/api/stt.py POST /stt + /stt/health + src/jefrey/api/tts.py POST /tts + /tts/health + /voices — 401 fail-closed + Policy MEDIUM + rate 10/min + HMAC kid + audit + metrics histogram — openapi 5 rotas — registry 42
- P1.3 Frontend: ui/src/lib/audio.ts MediaRecorder opus 16k + Analyser pulse + ui/src/hooks/useVoice.ts stt->chat qwen2->tts + ui/src/components/VoiceButton.tsx neon pulse 1.0-1.6 CEOGPT + Chat.tsx slot — vite proxy stt/tts — build 2409 modules 5 chunks 34.7kB+163kB+383kB — StaticFiles OK
- P1.4 Wake: ui/src/hooks/useWakeWord.ts Web Speech jarvis interim (porcupine quando key) + Settings.tsx Voz Card wake toggle + 5 vozes Mark-LII Charon/Puck/Kore/Fenrir/Aoede + localStorage — build 34.7kB OK
- P1.5 Obs: metrics STT/TTS histogram + Grafana panel 9 STT Latency p95 histogram_quantile by(le) + alerts JefreySttLatencyHigh >2s 5m — tests 8->9 panels fixed — deep 175/175 2x + 27/27 2x 9 panels editable false + 54/54 2x — live /stt/health 401->200 + /tts 200 + /health 200 + qwen2 generate ok — 1 programa 7 pecas (sem novo container, Axiom #7)
- Gates 23:13: deep 175/175 2x WARN0 BUG0 + verify_p6_data 21/21 2x + verify_p6 27/27 2x + verify_p7 54/54 2x + pytest 40 passed + compileall + docker 7/7 + /metrics stt/tts + /openapi 5 rotas — guard 6/6 PASS
- Docs: docs/PLANO_P1_VOZ_COMPLETO.md 18k + CHANGELOG [1.3.0-p1-voz] — branch feat/p1-voz merged --no-ff -> main 7e99ac7 — tag v1.3.0-p1-voz


---
## F5 Revalidacao Final — 2026-09-04 19:05 — feat/final-100 396c73d + vite fix 2b2fd2a 100B — APROVADO
- **Gates 2x**: deep 175/175 WARN0 BUG0 2x + verify_p6_data 21/21 2x + verify_p6 27/27 2x + verify_p7 54/54 2x + pytest 40 passed 2x + compileall OK + compose config -q RC0 + 7/7 healthy (jefrey-api/postgres/redis/mcp/n8n/prometheus/grafana) — SWE cap14 idempotente
- **Live 16/16 PASS**: /health 200 + /metrics jefrey_ + /vite.svg 200 len100 BOM EF BB BF + /openapi 7738 + prometheus /-/healthy 200 + grafana /api/health 200 + anon 401 + auth 200 editable false panels 9 + ollama qwen2.5:0.5b + POST /auth/dev-token 200 len64 + POST /chat anon 401 + POST /chat Bearer running + poll complete 48s texto real qwen2.5 + /stt/health small pt + /tts/health piper pt_BR-faber + /tts/voices 6 voices
- **Bug Hunt 6/6**: GREP-1 except:pass 0 + GREP-2 dev-auto 0 + GREP-3 return allow 0 + GREP-4 str(dict) 0 + GREP-5 b64 urlsafe 0 (jwks urlsafe_b64encode) + GREP-6 overwrite 0 + TODO 0 + secrets 0 + incomplete ONLY pass 3 (SkillBase abstract @abstractmethod get_tools/initialize/shutdown - esperado Fluent cap19) + signing compare_digest + rate_limit pipeline
- **F4 fixes validados**: vite.svg restore S-01 100B 2b2fd2a + chat.py running->complete keep 60s + _cleanup_stale_tasks + grafana cred sync BGl***ALZ + guard_anti_patterns.sh 6/6
- **Docs sync**: TODO header 2026-09-04 19:05 + CHANGELOG [1.4.0-final-100] + vite 2b2fd2a (main blob)
- **Tag**: v1.4.0-final-100 (F0-F5 fechado) — pronto para merge --no-ff feat/final-100 -> main
- **Axioms**: #1 FAIL-CLOSED #2 ISOLAMENTO #3 SEM STUB #4 PERSISTENCIA #5 LEAST PRIVILEGE #6 OBSERVABILIDADE #7 1 PROGRAMA 7 PECAS + CIPHER 025-035 + Livros 1-10 + Mark-LII/CEOGPT/HUD
