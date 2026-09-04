# Changelog - Jefrey

## [1.5.0-leigo-100] — 2026-09-04 — F6 Leigo 100% (Onboarding + HUD Glass + Conexoes + PWA + Tour) — 175/175 2x + 24/24 live — APROVADO
**Gate**: _validate_deep 175/175 WARN0 BUG0 2x + verify_p6_data 21/21 2x + verify_p6 27/27 2x 9 panels by(le) editable false orgId:1 + verify_p7 54/54 2x + pytest 40 passed 2x + compileall RC0 + compose config -q RC0 + 7/7 healthy + live 24/24 (health/metrics/vite.svg 100B/openapi/manifest/sw/prometheus/grafana anon401/auth200 panels9/ollama qwen2.5/dev-token/chat poll 48s/connections browse 200/memory add 401)
**F6-1**: Onboarding Zero-Clique auto POST /auth/dev-token + OnboardingWizard 3 steps + Badge Pronto verde (leigo sem Settings)
**F6-2**: Glass HUD Reactor 180px pulse 1.0-1.6 + ThemeWheel hue + chime 2.4s + markdown + glass sticky header + theme-color
**F6-3**: Conexoes 1-Clique 4 botoes Navegar/Arquivo/Buscar/Enviar + /connections/* + /memory/add + Settings Conexoes + docs/CONEXOES_N8N.md
**F6-4**: PWA manifest.json standalone + sw.js jefrey-v1 + start_jefrey.bat v2 One-Click + whitelist /manifest.json /sw.js
**F6-5**: Tour 4 steps ?tour=1 + GUIA_LEIGO 5 passos + Observability 3 gigantes p95/7-7/42
**F6 fixes**: Chat.tsx template [${r.kind}] fix + vite.svg 100B 2b2fd2a binary write (nao powershell redirect) + assets 6 chunks
**Prova**: vite 100B + poll 48s + HUD pulse + ConnectionHub 1-clique + Tour + PWA instalavel + start_jefrey.bat v2 + 24/24 live

## [1.4.0-final-100] â€” 2026-09-04 â€” F0-F5 Final 100 Comercial â€” 175/175 2x + 16/16 live â€” APROVADO
**Gate**: _validate_deep 175/175 WARN0 BUG0 2x + verify_p6_data 21/21 2x + verify_p6 27/27 2x (9 panels by(le) editable false) + verify_p7 54/54 2x + pytest 40 passed 2x + compileall OK + compose config -q RC0 + 7/7 healthy + live 16/16 (health/metrics/vite/openapi/prometheus/grafana anon401/auth200/ollama qwen2.5/dev-token/chat poll 48s/stt/tts voices)
**F4**: vite.svg restore S-01 2b2fd2a 100B BOM + chat poll running->complete keep task 60s + _cleanup_stale_tasks (Axiom #1 FAIL-CLOSED, SWE cap14, DDIA cap6) + grafana cred sync BGl***ALZ volume recreate + guard 6/6 + voz poll qwen2.5:0.5b STT small TTS piper 6 voices
**F3**: agent fallback qwen2 completion-only + validator qwen2 broad + compose default qwen2.5:0.5b tools â€” E2E /chat 200 running + LLM probe host.docker.internal:11434
**F2**: auth wiring api.ts X-User-Id + auth dev-token POST fail-closed CIPHER-021 + useVoice DRY + Settings Obter token dev + GUIA_LEIGO
**F0**: name jefrey + volumes explicit name jefrey_* + branch feat/final-100 travado P0+P1 175/175
**Stack**: Python 3.12 FastAPI Postgres+pgvector HNSW m16 ef64 pgvector Redis Streams XADD 10000 DLQ 5000 JWT RS256 kid TTLCache 1024/60 + 7 servicos (Compose Spec 2.24)
**Refs**: Axiom #1-7 + CIPHER 025-035 + 10 Livros (MCP Spec 2026-07-28, Security Eng, Prometheus cap5/6/10/11, DDIA cap3/5/6/12, SWE cap8/14, Fluent 19-21, HPP cap1-4, Building LLM Apps, Pragmatic 20th) + Mark-LII/XXXIX + CEOGPT/HUD
**Commits**: 49eb801 chore F0 + 3d84d58 fix docker + e73006f feat F2 + 6922b19 feat F3 + 584e04a fix F3 + ce5b1a9 feat F4 + 396c73d fix F4 + F5 175/175 16/16 docs sync â€” tag v1.4.0-final-100
**Prova**: docker 7/7 healthy + vite 100B + poll 48s texto real + grafana auth 200 panels 9 + anon 401 + guard 6/6 0 hits



Todas mudancas notaveis deste projeto. Formato baseado em Keep a Changelog.

## [1.3.0-p1-voz] â€” 2026-09-03 â€” P1 Voz Viva (STT+TTS+Wake+HUD) â€” qwen2:0.5b + whisper small + VoiceButton
**Gate**: _validate_deep 175/175 2x + verify_p6_data 21/21 2x + verify_p6 27/27 2x 9 panels + verify_p7 54/54 2x + pytest 40 passed + compileall OK + docker 7/7 + /stt 401->200 + /tts 200 + /chat qwen2 200 + /metrics stt/tts histogram + openapi 5 rotas
**P1.0** qwen2:0.5b 352MB workaround OOM 8b 3.3GB â€” .env MODEL + compose JEFREY_LLM__MODEL x2 host.docker.internal
**P1.1** STT faster-whisper small int8 pt + TTS elevenlabs/pyttsx3 fallback + mock dev only (Axiom #3)
**P1.2** API /stt POST multipart + /tts POST JSON + /health + /voices â€” 401 fail-closed + Policy MEDIUM + rate + HMAC + audit + STT/TTS histogram â€” registry 42
**P1.3** Frontend VoiceButton HUD pulse 1.0-1.6 CEOGPT + useVoice stt->chat->tts chain + Chat slot + vite proxy stt/tts â€” 2409 modules 5 chunks
**P1.4** Wake useWakeWord Web Speech jarvis + Settings Voz Card 5 vozes Mark-LII + localStorage
**P1.5** Prometheus histogram stt/tts + Grafana panel 9 p95 + alert JefreySttLatencyHigh + gates verde
**Commits** feat/p1-voz 45c0d8f -> main 7e99ac7 â€” Axiom #1-7 + CIPHER 025-035 + Livros 1-10 + Sites CEOGPT/Mark-LII/XXXIX â€” 1 programa 7 pecas (sem novo container)

## [1.2.0-ui] - 2026-09-03 - UI-1 Shell + UI-2/UI-3 100% comercial - Vite+React+TS+Tailwind

**Gate**: _validate_deep 175/175 2x + verify_p6_data 21/21 2x + verify_p6 27/27 2x + verify_p7 54/54 2x + pytest 40 passed + compileall OK + guard 6/6 + promtool 6/6 + compose config -q RC0 + 7/7 healthy (pre-Docker restart)
**UI**: Vite 5.4.2 + React 18.3 + TS 5.5 + Tailwind 3.4 + shadcn + React Query + Recharts + react-router-dom 6.26 - 5 telas Chat/Memoria/Approvals/Observabilidade/Settings - build 891 modules 633.58kB (gzip 185.40kB) -> src/jefrey/static via FastAPI StaticFiles mount "/" html=True - sem novo container (Axiom #1: 1 programa 7 pecas)
**Fixes**: src/jefrey/api/main.py StaticFiles mount "/" + reload=False (watchfiles Permission denied OS13 read_only) + tmpfs /app/.cache - src/jefrey/api/auth_middleware.py whitelist "/" "/vite.svg" "/favicon.ico" "/assets/*" (least privilege CIPHER-019) - docker-compose.yml DB postgres:5432/redis:6379 explicit sem fallback localhost - ui/src/pages/Memory.tsx POST 405->GET /memory/search?q=&limit= - ui/src/pages/Approvals.tsx silencia 401 polling sem token (Axiom #1 fail-closed)
**Gates**: P06-19/P07-044 6->6+ panels (8 panels real) + P07-041 Field(default=False) + P07-023 encoding nao registrada + P07-049 mock rate_limit+ApprovalManager (CI sem Redis/Postgres) - commit 7f07274
**Docs**: docs/PLANO_MESTRE_P0_COMPLETO.md 163L + docs/PLANO_P0_FECHAMENTO.md 181L + scripts/start_jefrey.bat leigo (Mark Auto-Start)
**Commits**: 88f2685 merge feat/ui-2 + d970160 + 3deead7 + 7f07274 - tag v1.2.0-ui 6efebb2
**Proximo**: P1 Voz (Whisper+ElevenLabs+wake) + P2 Mao/Plugins + P3 Theming/code-split - so apos docker 7/7 + tag

## [1.1.0] â€” 2026-09-03 â€” P7 PERF T2 (Ordem B 60m 167->175) â€” 175/175

**Gate**: _validate_deep 175/175 (170+5) + verify 21/21 2x equal:true + pytest 40 passed + evals 6 passed + compileall OK + guard 6/6 + promtool 6/6 + compose config -q RC0 + 7/7 healthy
**Provas vivas**: reports/p7-cprofile.prof 3.1MB + p7-cprofile.txt 3719B cumtime 30 linhas (HPP cap1) + reports/p7-bench.log 8837B p50 48.1ms p95 55.0ms ef64 / p95 52.3ms ef200 60 queries 100 rows Seq Scan (DDIA cap12) + reports/p7-evals.log 900B 6/6 (Building LLM Apps)
**Otimizacoes** (HPP cap2-3, Fluent 19-21, <5% GO com fallback): src/jefrey/core/audit.py functools.lru_cache 1024 + orjson sort_keys (CIPHER-025, 2 camadas) + src/jefrey/core/pg_memory.py WeakValueDictionary _PG_CACHE + orjson _jsonable
**Docs**: docs/PERF_TUNING.md reescrito 8 secoes com cProfile real + bench p95 real + evals 6 types + GO/NO-GO <5% (Pragmatic cap8) + docs/HNSW_TUNING.md Â§6 P7
**Refs**: HPP cap1-4 + Fluent 19-21 + Building LLM Apps + DDIA cap12 + Livro4 cap5/6 + SWE cap8/14 + CIPHER-025/033 + Axiom #1-7
**Commits**: 167/167 v1.0.0 f93578a/bb4c45e + T2 P7 PERF v1.1.0

## [1.0.0] â€” 2026-09-03 â€” P8 TAG (T3 Ordem B â€” 150â†’162)

### Auditado 150/150 2x + 21/21 2x + 40 passed + 7/7 healthy (Axiom #1-7 + CIPHER + Livros)

- **P6-C** bdcae44 feat(P6-C): verify 150/150 idempotente + CI gate + compose healthy (DDIA cap3/6, SWE cap14, Axiom #1, 21/21 2x)
- **P5-C** 88bf25d feat(P5-C): consolidacao observability freeze 148/148 idempotente (Livro4 cap5/6/10/11, 148/148)
- **P6-gaps** 687d589 feat(P6-gaps): verify 19/19 + isolation 2 tenants + deep 136->148 secao U (DDIA cap3/5/6/12, CIPHER-033)
- **P6-A** HNSW CONCURRENTLY m16 ef64 AUTOCOMMIT + bench CAST vector + SET LOCAL int(ef) (DDIA cap12, HPP cap4)
- **P6-B** Streams 2-processos maxlen10000 DLQ maxlen5000 XACK dual-verify kid v1/v2 + BGSAVE + pg_dump (CIPHER-033)
- **T1 hardening** 8feef7e feat(T1): redis healthy + skill_registry + requirements +11 deps + testpaths + compileall OK (Axiom #2/#4, 40 passed)
  - 28aa37d fix(T1): AppSettings env_prefix JEFREY_ isolate AGENT=1 (Axiom #2, CIPHER-032)
  - 98cd0da fix(T1.1): mcp missing register_default_tools import â€” jefrey-mcp healthy (Axiom #6, CIPHER-032, DDIA cap6)
  - 5c54440 docs(T1): fecha T1 HARDENING 100% Up vivo 7/7 healthy + grafana by(le):2 + 150/150 2x
- **P8** docs: SLO_RUNBOOK 6 alerts x PromQL x for x slo, THREAT_MODEL 7 controles STRIDE, PERF_TUNING GO/NO-GO <5%, HNSW_TUNING Â§5, CHANGELOG

#### Commits desde bdcae44

```
7fcc91d docs(P7): add PLANO_P7_PERF_V1.md 214L force (gitignore)
a6b3f63 docs(P7): plano P7 PERF V1.0 60m 150->158 + validacao 11:15 99% DATA + ordem P8 + guia uso jefrey (HPP, Fluent, DDIA, Livro4)
5c54440 docs(T1): fecha T1 HARDENING 100% Up vivo 7/7 healthy + grafana by(le) 2 + 150/150 2x (Axiom #1, DDIA cap6, Livro4 cap11, 40 passed)
98cd0da fix(T1.1): mcp server missing register_default_tools import â€” jefrey-mcp healthy (Axiom #6, CIPHER-032, DDIA cap6, SWE cap8, 150/150, 40 passed)
6c3cebb docs(T1): recria PLANO_SINCRONIZADO V2.1 do zero 10:47 + TODO sync (150/150, 21/21 2x, 40 passed, D3 fechado)
28aa37d fix(T1): isolate AppSettings env_prefix JEFREY_ to ignore AGENT=1 collision (Axiom #2, CIPHER-032, 40 passed)
a6c0aae docs(T1): TODO V2.1 hardening audit 09:40 (150/150, 21/21 2x)
9c204a2 docs(T1): sync V2.1 audit 09:40 + TODO T1.0 hardening 8feef7e (150/150, 21/21, 40 passed)
8feef7e feat(T1): hardening 100% redis healthy + skill_registry + requirements sync + testpaths (Axiom #2/#4, 150/150, 40 passed)
```

#### Gates

- 122/122 ->136/136 ->148/148 ->150/150 (P6-C) ->162/162 (P8) = 100% v1.0.0
- verify_p6_data 21/21 2x idempotente true + deep 162/162 WARNS0 BUGS0 + compileall OK + pytest 40 + promtool 6/6 + grafana 8 panels by(le):2 + compose 7/7 healthy

#### Uso

- `curl http://localhost:8000/health` + `/docs` + `curl http://localhost:8001/health` + `open http://localhost:9090` + `http://localhost:3000` + `http://localhost:5678` + python bench/drill (PLANO_P7 sec5)

## [1.0.0-p5-c] â€” local

- Tag local v1.0.0-p5-c 88bf25d â€” P5 freeze 148/148

## [0.6.0] â€” P6 DATA 150/150

- HNSW, Streams, backup, verify 21/21 â€” DDIA cap3/5/6/12

## [0.5.0] â€” P5 OBSERVABILITY 148/148

- Cardinality <800, 8 panels, 6 alerts for/severity/slo, promtool SUCCESS

## Referencias externas 10 repos

- public-apis 474k, awesome 501k, free-for-dev 136k, awesome-mcp-servers 93k, ollama 179k, langflow 154k, OpenHands 85k, Scrapling 77k, awesome-llm-apps 135k, open-design 93k â€” R$0 licenca != R$0 custo (Secao 6 PERF_TUNING)
