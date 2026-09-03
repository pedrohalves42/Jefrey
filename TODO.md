# TODO Pre-codar — 2026-09-03 18:08 — base 175/175 + feat/ui-shell merged em main (0339dd7)

## Base ja fechada (nao mexer sem branch)
- [x] T1 HARDENING 100% + T3 P8 TAG v1.0.0 167/167 + T2 P7 PERF v1.1.0 175/175 + D5 push origin/main 11c864c + 3 tags (v1.0.0, v1.0.0-p5-c, v1.1.0)
- [x] feat/cleanup-100 merged de2fe1f (93 obsoletos + fix ci grep) -> 175/175
- [x] feat/ui-shell 0339dd7 merged -> main (Vite+React+TS build -> src/jefrey/static, FastAPI StaticFiles mount /, whitelist / + /assets/*, reload=False + tmpfs /app/.cache) — 7/7 healthy, / 200 HTML, /chat 401

## Checklist ANTES de codar (ordem ideal — Axiom #1 FAIL-CLOSED, SWE cap14, DDIA cap6)
- [x] 1. Validar CI remoto/local: guard 6/6 + pytest 40 + evals 6 + promtool 6/6 — PROVADO 2026-09-03 22:15 feat/ui-2 175/175 2x 21/21 2x 46 7/7 + compose host fix + Memory GET
- [x] 2. Proteger main: branch feat/ui-2 usada — NAO codado direto em main (merge --no-ff)
- [x] 3. Validar ambiente local: docker compose ps 7/7 healthy (api/mcp/postgres/redis/prometheus/grafana/n8n) + compose config -q RC0 + .env presente + tmpfs /app/.cache + reload=False + DB postgres:5432
- [x] 4. Re-validar gates locais 2x: deep 175/175 2x + verify 21/21 2x + pytest 46 + compileall -q — PROVADO idempotente + live / 200 + /chat 401->200 Ollama (esperado) + /memory/search GET 200
- [x] 5. Alinhar proximo escopo: PLANO_FEAT_UI_UI2 285L UI-1..UI-3 feat/ui-2 merged — 100% comercial (Axiom 1-7 CIPHER Livros 1-10)
- [x] 6. Sincronizar docs: TODO.md + PLANO_FEAT_UI_UI2 + CHANGELOG alinhados feat/ui-2

## Depois do checklist -> feat/ui-2 100% comercial FECHADO 2026-09-03 22:15 — proximo: CI verde em main -> tag v1.2.0-ui

## Estado final feat/ui-2 + host fix + Memory GET -> main
- deep 175/175 WARN0 BUG0 2x (98-99% codigo OK - P6-C 150/150 fechado)
- verify 21/21 2x 100% DATA OK
- pytest 40 + evals 6 =46 passed + compileall OK + guard 6/6 + grafana editable false + by(le) + ci grep ok
- docker 7/7 healthy + compose config -q RC0 + DB host postgres:5432 redis:6379 (fix 500 psycopg localhost)
- live: / 200 HTML tmSQPxDU 633kB, /health 200, /docs 200, /assets 200, /vite.svg 200, POST /chat no-auth 401 + with Bearer 500 Ollama (sem Ollama rodando, nao bug DB), GET /memory/search?q= 200
- git: feat/ui-2 -> main merged --no-ff, origin/main + feat/ui-2 pushed, 100% comercial (leigo so http://localhost:8000/ sem /docs)
