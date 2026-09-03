# TODO Pre-codar — 2026-09-03 18:08 — base 175/175 + feat/ui-shell merged em main (0339dd7)

## Base ja fechada (nao mexer sem branch)
- [x] T1 HARDENING 100% + T3 P8 TAG v1.0.0 167/167 + T2 P7 PERF v1.1.0 175/175 + D5 push origin/main 11c864c + 3 tags (v1.0.0, v1.0.0-p5-c, v1.1.0)
- [x] feat/cleanup-100 merged de2fe1f (93 obsoletos + fix ci grep) -> 175/175
- [x] feat/ui-shell 0339dd7 merged -> main (Vite+React+TS build -> src/jefrey/static, FastAPI StaticFiles mount /, whitelist / + /assets/*, reload=False + tmpfs /app/.cache) — 7/7 healthy, / 200 HTML, /chat 401

## Checklist ANTES de codar (ordem ideal — Axiom #1 FAIL-CLOSED, SWE cap14, DDIA cap6)
- [x] 1. Validar CI remoto/local: guard 6/6 + pytest 40 + evals 6 + promtool 6/6 — PROVADO local 2026-09-03 18:08 (deep 175/175 2x + verify 21/21 2x + 40+6 passed + compileall + grafana editable false + ci grep ok)
- [x] 2. Proteger main: branch feat/ui-shell usada — NAO codado direto em main (merge --no-ff)
- [x] 3. Validar ambiente local: docker compose ps 7/7 healthy (6 healthy + grafana running) + compose config -q RC0 + .env presente — PROVADO 16min up
- [x] 4. Re-validar gates locais 2x: deep 175/175 2x + verify 21/21 2x + pytest 46 + compileall -q — PROVADO idempotente
- [ ] 5. Alinhar proximo escopo: definir PLANO do proximo ciclo (UI-2 Chat+Memory 90m + UI-3 HITL+Obs 60m) com Axiom #1-7 + CIPHER + Livros ref — sem quebrar 175/175 (PROXIMO)
- [ ] 6. Sincronizar docs: TODO.md + PLANO_SINCRONIZADO + CHANGELOG alinhados antes do primeiro commit da proxima feature (PROXIMO)

## Depois do checklist -> criar branch feat/ui-2 + codar UI-2/UI-3 mantendo 175/175

## Estado atual validado 2026-09-03 18:08
- deep 175/175 WARN0 BUG0 2x (98-99% codigo OK - P6-C 150/150 fechado)
- verify 21/21 2x 100% DATA OK (DDIA + CIPHER-033 + Livro4 cap5)
- pytest 40 passed + evals 6 passed = 46 (4 warnings chromadb/pythonjsonlogger)
- compileall OK, guard 6/6 via pre-commit (WSL bash fallback), grafana editable false + by(le) true, ci grep ""editable": false" OK
- docker 7/7 healthy: jefrey-api 16m healthy, postgres 25h healthy, redis 9h healthy, mcp/prometheus healthy, grafana/n8n running, compose config -q RC0, tmpfs /app/.cache + reload=False
- live: GET /health 200 {"status":"ok","version":"0.1.0"}, GET / 200 HTML Jefrey 1 programa 7 pecas, GET /docs 200, POST /chat sem token 401 fail-closed, /assets 200
- git: feat/ui-shell 0339dd7 -> main merged, origin/main pendente push, remote https://github.com/pedrohalves42/Jefrey.git
