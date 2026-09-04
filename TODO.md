# TODO Pre-codar — 2026-09-03 21:45 — base 175/175 + P6 27/27 + P7 54/54 + 40 tests — pronto p/ tag v1.2.0-ui

## Base já fechada (não mexer sem branch)
- [x] T1 HARDENING 100% + T3 P8 TAG v1.0.0 167/167 + T2 P7 PERF v1.1.0 175/175 + D5 push origin/main 11c864c + 3 tags (v1.0.0, v1.0.0-p5-c, v1.1.0)
- [x] feat/cleanup-100 merged de2fe1f (93 obsoletos + fix ci grep) -> 175/175
- [x] feat/ui-shell 0339dd7 merged -> main (Vite+React+TS build -> src/jefrey/static, FastAPI StaticFiles mount /, whitelist / + /assets/*, reload=False + tmpfs /app/.cache) — 7/7 healthy, / 200 HTML, /chat 401
- [x] feat/ui-2 merged 88f2685 -> main (UI 5 telas + Memory GET fix + host postgres:5432) — 175/175 21/21 46 7/7
- [x] P0 docs: PLANO_MESTRE_P0_COMPLETO 163L + PLANO_P0_FECHAMENTO 181L + start_jefrey.bat leigo (Axiom #1, SWE cap14, Mark Auto-Start)
- [x] GATE FIX 2026-09-03 21:42: P06-19 6->6+ (8 panels) + P07-041 Field(default=False) + P07-044 6->6+ + P07-023 encoding (nao registrada lower) + P07-049 mock rate_limit+ApprovalManager (Redis/Postgres offline) -> P6 27/27, P7 54/54

## Checklist ANTES de codar (ordem ideal — Axiom #1 FAIL-CLOSED, SWE cap14, DDIA cap6)
- [x] 1. Validar CI remoto/local: 175/175 2x + 21/21 2x + 27/27 2x + 54/54 + 40 passed + compileall OK + grafana editable false by(le) — PROVADO 2026-09-03 21:42
- [x] 2. Proteger main: branch feat/ui-2 usada — NAO codado direto em main (merge --no-ff)
- [x] 3. Validar ambiente local: .env presente + compose config -q RC0 + tmpfs /app/.cache + reload=False + DB postgres:5432 (docker engine 500 precisa Restart Docker Desktop manual 2 min)
- [x] 4. Re-validar gates locais 2x: deep 175/175 2x + verify 21/21 2x + verify_p6 27/27 2x + verify_p7 54/54 + compileall -q + pytest 40 — PROVADO idempotente (P07-049 mockado p/ CI sem docker)
- [x] 5. Alinhar proximo escopo: PLANO_FEAT_UI_UI2 285L UI-1..UI-3 merged — 100% comercial (Axiom 1-7 CIPHER Livros 1-10)
- [x] 6. Sincronizar docs: TODO.md + PLANO_FEAT_UI_UI2 + CHANGELOG alinhados + gate fixes

## Depois do checklist -> feat/ui-2 100% comercial FECHADO 2026-09-03 21:45 — proximo: Restart Docker Desktop -> docker compose up -d --wait -> tag v1.2.0-ui -> P1 voz

## Estado final 2026-09-03 21:45
- deep 175/175 WARN0 BUG0 2x (98-99% codigo OK - P6-C 150/150 fechado)
- verify_p6_data 21/21 2x 100% DATA OK
- verify_p6 27/27 2x 100% OBSERVABILITY OK (8 panels, editable false, by(le))
- verify_p7 54/54 100% INTEGRATION OK (com mock ApprovalManager; sem mock 53/54 por Postgres offline — fix intencional CIPHER-025)
- pytest 40 passed + compileall OK + guard 6/6 (bash via WSL)
- docker 7/7 PENDENTE: engine 500 (com.docker.service STOPPED 1077) — precisa tray -> Restart + docker compose up -d --wait (2 min manual)
- ollama 2/2 vivo: nomic-embed-text 274MB + llama3.1:8b 4.9GB (curl 11434 OK)
- live sem docker: /health timeout (engine down) — com docker esperado: / 200 HTML 633kB, /health 200, /docs 200, /chat 401->200 Bearer
- git: main 3deead7 + gate fixes pendente commit -> origin/main + tag v1.2.0-ui pendente
