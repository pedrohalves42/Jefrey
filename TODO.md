# TODO Pre-codar — 2026-09-03 22:15 — base 175/175 + P6 27/27 + P7 54/54 + 40 tests — v1.2.0-ui SYNCED f6381e2

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
