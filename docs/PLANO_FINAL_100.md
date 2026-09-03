# PLANO FINAL 100% — Jefrey Comercial (pos-cleanup 175/175) — 2026-09-03
> Base: feat/cleanup-100 — deep 175/175 2x + verify 21/21 2x + 40+6 passed 46 + compileall OK + 7/7 healthy + guard 0 hits — 93 obsoletos removidos

## 1) Revisao arquivos — uteis vs obsoletos (executada)
### Mantidos (Axiom #1 FAIL-CLOSED)
- src/jefrey/** 59 py ~11k lines (api, core, eventbus, mcp, oauth2, skills, interfaces)
- tests/** 11 + evals/test_memory_types.py (6 types Building LLM Apps)
- docs/{SLO_RUNBOOK,THREAT_MODEL,PERF_TUNING,HNSW_TUNING,METRICS_CARDINALITY,P5_CONSOLIDATION,GUIA_LEIGO,REFERENCES,ADRs,oauth}
- scripts/{_validate_deep,verify_*,bench_hnsw,drill_*,guard_*,setup,smoke_test,start_jefrey.*}
- docker/{grafana,prometheus} + docker-compose.yml + .github/workflows/ci.yml|test.yml + n8n/workflows + config/**
- JEFREY-AUDIT/** 25 md historico (nao apagar)
- reports/p7-* + p6-* provas vivas versionadas
- PLANO_SINCRONIZADO_P0_P8_V2.md + PLANO_T2_P7_PERF_V2.md + PLANO_P7_PERF_V1.md + PLANO_FASE_P5-*.md (fixos .gitignore)

### Removidos 93 (commit anterior)
- Root tracked 14: check_config.py, show_agent.py, show_config_lines.py, test_agent.py, test_config.py, test_debug.py, test_final_validation*.py, test_full_agent.py, test_memory.py, test_phase1*.py, test_simple.py, test_skills.py
- src/jarvis/** 10 py legacy (substituido por src/jefrey, ultimo uso 26aa1aa)
- Duplicatas raiz SLO_RUNBOOK.md + THREAT_MODEL.md -> canonico docs/
- Planos antigos ignorados 10: FASE1_CRITICO, FASE2_ALTO, FASE3_MEDIO, FASE4_BAIXO, FASE_P4_PROD, FASE_P6-B, MESTRE_44, UNIFICADO, REFERENCES_MAPPING, RESUMO_JARVIS
- Temporarios 16: audit_pessimista.py, audit_v2_falsos_verdes.py, check_deps*.py, p3_*.py, test_cipher*.py, etc
- Scripts temp 8: _fix_*.py, _verify_*quick, _validate_e1_full, mcp_n8n_client, fix_pyproject_httpx
- Reports junk 30: test_run_*.md 29 + junit.xml + p5-04-drill-2.log
- Artefatos: docs/security-audit/.venv 5145 files + logs/ + __pycache__ + .pytest_cache + 0.20.0

### Por que nao quebrou
- Cada delecao validada por _validate_deep: docs/ continua 175/175, src/jefrey intacto, CI usa so tests/+evals/
- Patch validate_deep N/Q: SLO/THREAT raiz -> docs/ + append P5-04

## 2) Bugs encontrados e corrigidos
| # | Bug | Fix (Axiom/CIPHER/Livro) | Status |
|---|-----|--------------------------|--------|
|1| Validate contava THREAT/SLO na raiz (deletados) | patch docs/* | FIXED 173->174 |
|2| WARN P5-04 SLO appendix faltava P5-04 | append Appendix P5-04 Livro4 cap10 | FIXED 174->175 |
|3| src/jarvis dirs vazios apos git rm | rmtree | FIXED |
|4| Legado jarvis divergente jefrey | git rm src/jarvis | FIXED |
|5| 45 prints em src (debug) | mantido logger CONFIG_VALID CIPHER-019 NAO bug | TRIAGED |
|6| TODO OAuth Google Calendar | deferido pos-UI | DEFERRED |
|7| ui/ vazio 0 .tsx | plano UI-1/2/3 abaixo | GAP COMERCIAL |

Gates apos fix: deep 175/175 WARN0 BUG0 + verify 21/21 2x + 40+6 46 + compileall True + guard 0 hits + compose 7/7 healthy

## 3) Falta para 100% comercial (70%% -> 100%%)
| Gap | Hoje | Plano |
|-----|------|-------|
| UI grafica zero | ui/components vazio | UI-1/2/3 60+90+60m |
| Onboarding sem UI | start_jefrey so /docs | UI serve em / + badge 7/7 |
| Auth sem login | Bearer/JWKS sem tela | UI login + refresh |
| HITL sem tela | /approvals sem UX | UI Approvals queue |
| Obs sem UI | Grafana separado | UI SLO cards by(le) |

## 4) Plano interface bonita — feat/ui-shell (Axiom #1)
Stack: Vite+React+TS+Tailwind+shadcn/ui+React Query+Recharts -> src/jefrey/static servido por FastAPI StaticFiles em /, sem novo container. CORS fail-closed, sem user_id label (Livro4 cap5).

Telas MVP: 1 Chat thread_id+HITL 2 Memoria vetorial p95 3 Approvals pending/decide 4 Observabilidade 4 cards 5 Settings 7/7 + links :3000/:9090/:5678

Sprints: UI-1 Shell 60m Vite+mount+/health | UI-2 Chat+Memory 90m /chat+content_guard+/memory | UI-3 HITL+Obs 60m /approvals+SLO histogram_quantile by(le) — cada sprint deep 175/175 + verify + guard + promtool

DONE: start_jefrey.bat duplo-clique -> http://localhost:8000/ Chat funciona + leigo aprova HITL sem /docs + 7/7

## 5) Correcao bugs ocultos (axiom/cipher/livros)
- Rodar _validate_deep 175/175 2x + verify 21/21 2x + guard 6 + promtool + compose -q cada sprint SWE cap14
- P5-01 cardinality nunca user_id labelnames (Livro4 cap5, CIPHER-026/033)
- P5-02/03 promtool+gendarme editable:false orgId:1 by(le) Livro4 cap10/11
- P6-C streams XADD 10000 + mkstream + DLQ 5000 DDIA cap6
- HNSW m16 ef64 ef_search 64 SET LOCAL int(ef) CAST vector DDIA cap12 HPP cap4
- Perf cProfile pstats + bench p50 48ms p95 55ms HPP cap1
- STUB proibido JEFREY_ENV prod validate_for_production 8 envs ?required valid_ _is_prod Axiom #1

## 6) Proximos passos 5 min
1 git push origin feat/cleanup-100 + merge main
2 validar CI verde
3 git checkout -b feat/ui-shell
4 scaffold UI-1
