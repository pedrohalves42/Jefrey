# PLANO SINCRONIZADO P0→P8 V2.1 — PÓS-AUDIT 2026-09-03 09:40 — P6-C 150/150 → 100% v1.0.0
> **Estado auditado agora:** P6-C 150/150 FECHADO (bdcae44) + P5-C 148/148 (88bf25d) + P6-gaps 148/148 (687d589)
> **Audit vivo 09:40:** verify_p6_data 21/21 2× idempotente 100% DATA OK + deep 150/150 98-99% + pytest 40 passed (tests -q e -q iguais) + compileall RC0 + compose config -q RC0 (dummy prod) + promtool check 6 rules SUCCESS + test rules SUCCESS + redis healthy / postgres healthy / prometheus healthy
> **Working tree suja:** 5 arquivos não commitados bloqueando Up healthy → T1 HARDENING pendente de commit
> **Objetivo:** fechar 100% antes de P7/P8. Sem T1, P7/P8 = otimização prematura sobre fundação não provada (SWE cap14 + HPP cap1)
> **Refs:** Axiom #1-7 + 6 FAIL-CLOSED | CIPHER 021/025/026/028/029/031/032/033/035 | Livros 1,2,3 AGORA → 4,5,6 DURANTE P8 → 7,8,9,10 DEPOIS | DDIA cap3/5/6/12 | Livro4 cap5/6/10/11 | SWE cap8/14 | Fluent 19-21 | HPP cap1-4

---

## 0) DIAGNÓSTICO PESSIMISTA — % REAL (axiom + cipher + livros)

### O que funciona — PROVADO neste audit (não opinião)
| Evidência | Prova 09:40 |
|---|---|
| **P6-C 150/150** | `scripts/_validate_deep.py` OKS:150 WARNS0 BUGS0 2× + `verify_p6_data.py` 21/21 2× stdout igual 100% DATA OK |
| **P5-C 148/148** | `docs/P5_CONSOLIDATION.md` freeze 6 alerts × PromQL × for × slo + 8 panels |
| **Isolamento** | `tests/test_p6_isolation.py` 2/2 + PolicyEngine guest/user/admin HITL UNKNOWN fail-closed |
| **HNSW** | schema.py AUTOCOMMIT + 4× CONCURRENTLY IF NOT EXISTS m=16 ef=64 + bench CAST(:emb AS vector) + SET LOCAL int(ef) |
| **Streams kid** | signing.py JEFREY_EVENTBUS__HMAC_KEYS_JSON v1/v2 dual-verify + v0 DeprecationWarning + EVENTBUS_KID_LEGACY_TOTAL [] |
| **Backup DDIA cap3** | reports/p6-backup.log pg_dump RC0 + BGSAVE ok — verify lê log fail-closed WARN se offline |
| **Cardinality cap5** | 18 métricas <800 séries global (sem user_id) — labelnames=[tool_name,decision] e [] |
| **Guard** | guard_anti_patterns.sh 6/6 (após T1 commit prova) + metrics_no_user_id + guard_grafana |
| **Compose config** | `docker compose config -q` RC0 com 8 dummy prod envs (DDIA cap6) |
| **CI gate** | ci.yml verify_p6_data 2× antes Guard + audit prod + pytest + compose config |
| **Pre-commit** | hook verify-p6-data always_run 2× |
| **Testes** | pytest tests -q 40 passed + pytest -q 40 passed (testpaths fix) strict asyncio_mode |
| **Promtool vivo** | check rules 6 rules SUCCESS + test rules SUCCESS (prom/prometheus:v2.53.0) — D3 FECHADO |
| **Infra healthy vivo** | jefrey-redis Up 15m healthy + jefrey-postgres Up 16h healthy + jefrey-prometheus Up 26m healthy |

### % pessimista por fase
| Fase | % | Justificativa pessimista |
|---|---|---|
| P0 Guardrails | 99% | 6 greps + pre-commit provados; falta commit T1 para fechar 100% |
| P1 MCP Spec | 95% | ctx reorder + RateLimiter deny ok; IdP real só P8 |
| P2 Auth/JWKS | 96% | urlsafe_b64encode RS256+kid ok; valid_ stub dev-only gate P8 |
| P3 Isolation | 98% | 2 tenants OK; dual sys.path drills ok |
| P4 Observability base | 97% | 6 alerts for/severity/slo + rule_files + 8 panels editable false |
| P5 freeze | 100% | P5-C 148/148 2× |
| P6 DATA | 99% | 150/150 + 21/21 + 40 passed; falta T1 commit + Up vivo completo (api/mcp) |
| P7 PERF | 10% | NÃO iniciado — propositalmente adiado (Axiom #1) |
| P8 TAG | 35% | Promtool D3 fechado, compose dummy OK; falta CHANGELOG + tag push + Up --wait vivo |
| **GLOBAL** | **94% → 99% após T1 commit** | Código 98-99% OK; produto 94% sem T1 commit, 99% com T1, 100% só após P8 162/162 |

### Gaps reais que IMPEDEM 100% hoje
1. **T1 sujo — 5 arquivos não commitados:** `Dockerfile.mcp` (dedup COPY), `docker-compose.yml` (redis env_file+env), `pyproject.toml` (testpaths), `requirements.txt` (+11 deps), `src/jefrey/skills/__init__.py` (skill_registry SkillBase) — sem commit, `git status --porcelain` sujo bloqueia tag (SWE cap14)
2. **jefrey-api / jefrey-mcp não provados vivo:** `docker ps` só mostra postgres/redis/prometheus + supabase; api/mcp não estão Up — precisam `docker compose build + up -d --wait` após T1 commit (DDIA cap6). Build anterior timed out 300s.
3. **D3 promtool — AGORA FECHADO:** re-run vivo SUCCESS 6/6 provado neste audit (check + test RC0) → marcar D3 como feito
4. **D4 Grafana by(le):** pendente confirmar `by(le)` count — guard requer ≥1, spec ≥2. Verificar jefrey.json 8 panels hist_quantile by(le) (Livro4 cap6)
5. **D5 push tag:** v1.0.0-p5-c local não pushado; v1.0.0 final pendente (P8)

---

## 1) PRINCÍPIOS INEGOCIÁVEIS

**Axiom 6 FAIL-CLOSED:** FAIL-CLOSED deny/false/raise | ISOLAMENTO user_id=None→guest + _build_filter mandatory + topic jefrey.events.{user_id}.{tool} + DLQ jefrey:dlq:{user_id} | SEM STUB EM PROD JEFREY_ENV dev/prod + validate_for_production() | PERSISTÊNCIA REAL setex pipeline incr/expire TTLCache só dev | CRIPTO urlsafe_b64encode sem padding RS256+kid aud/iss/exp/kid/alg compare_digest sort_keys kid rotation v1→v2 | LEAST PRIVILEGE overwrite=False :ro CORS explicit enumerated allow_credentials False pool_pre_ping pool_recycle 3600

**CIPHER:** 021 silent except | 025 dual-write audit Postgres→data/audit_fallback.jsonl redact_pii 2 camadas | 026 rate limiting pipeline | 031 JWKS/introspect | 032 Skill Risk | 033 HMAC kid v1/v2 dual-verify | 035 Token Refresh | 010 audit | 028/029 policy

**Livros ordem:** 1 MCP Spec 2026-07-28 > 2 OpenAI Agents Cookbook > 3 Security Engineering > DURANTE P8: 4 Prometheus cap5/6/10/11 > 5 DDIA cap3/5/6/12 > 6 SWE cap8/14 > DEPOIS: 7 Fluent 19-21 > 8 HPP > 9 LLM Apps > 10 Pragmatic

**Qualidade (SWE cap8):** py_compile + compileall -q + ruff/mypy + sem str(dict) sem b64encode sem urlsafe sem overwrite=True sem In-memory prod sem :-jefrey sem .:/app sem :ro

---

## 2) MAPA DE GATES

| Gate | Total | Quando | Adiciona |
|---|---|---|---|
| 90/91 | 91 | P4 | base |
| 95/95 | 95 | P4-05 | +5 Q HOTFIX |
| 108/108 |108| P5-04/05/06 | +13 R/S/T |
| 122/122 |122| P5-01/02/03 | +14 observability |
| 136/136 |136| P6-A/B | +14 HNSW+Streams+backup |
| 148/148 |148| P6-gaps+P5-C | +12 U |
| **150/150** |**150**| **P6-C bdcae44** | **+2 V verify 21/21 2× (ATUAL)** |
| 158/158 |158| P7 PERF | +8 HPP/Fluent/Evals |
| 162/162 |162| P8 TAG | +4 SWE deploy+docs |

Regra: nunca 158 sem 150/150 2× + compose config RC0 + 40 passed. Nunca tag sem 162/162.

---

## 3) PLANO SINCRONIZADO — 3 TRACKS SEQUENCIAIS (135m)

### TRACK 0 — Sincronização contínua (toda task, 0.5m)
- Antes: `git status --porcelain` clean + `verify_p6_data.py` 2× 21/21 + `_validate_deep.py` 150/150
- Depois: `py_compile` + `compileall -q src` + `guard_anti_patterns.sh` 6/6 + `_validate_deep.py` 150/150 (ou 158/162)
- Commit: `feat(Px): <o que> — refs Axiom# CIPHER-xxx LivroY capZ` + `add -f` se PLANO_*/reports/*
- Nunca quebrar: isolamento → fail-closed → cardinality → HNSW CONCURRENTLY → kid dual-verify → backup

### TRACK 1 — P6-C HARDENING (15m) — PRÓXIMO, FECHA 99%→100% DATA
**Objetivo:** zerar working tree suja, provar Up healthy vivo completo, fechar D4, sem regressão 150/150

- [ ] **T1.0 (2m) Commit hardening — BLOQUEANTE:** `git add Dockerfile.mcp docker-compose.yml pyproject.toml requirements.txt src/jefrey/skills/__init__.py` + `git commit -m "feat(T1): hardening 100% redis healthy + skill_registry + requirements sync + testpaths (Axiom #2/#4, 150/150, 40 passed)"` — working tree deve ficar clean. Critério: `git status --porcelain` vazio + `git diff --stat` 0
- [ ] **T1.1 (5m) Up vivo completo:** `docker compose build jefrey-api mcp-server` (split se timeout 300s → build --no-cache por serviço) + `docker compose up -d --wait` + `docker ps --format table` provar 5/5 healthy: postgres, redis, jefrey-api, mcp-server, prometheus (grafana se habilitado). Healthcheck redis fallback `-a` já no yml via T1.0. — DDIA cap6. Se build timeout, fazer `docker compose build jefrey-api` separado de `mcp-server`.
- [ ] **T1.2 (2m) Grafana by(le) drift — fecha D4:** `python -c "import json; d=json.load(open('docker/grafana/dashboards/jefrey.json')); print(sum(1 for p in d['panels'] if 'by(le)' in str(p)))"` → garantir ≥2 panels com `sum by(le)` (Livro4 cap6). Se 1, corrigir 2º painel hist_quantile + `guard_grafana.sh` 8 panels editable false uid jefrey-main. Commit `fix(T1): grafana by(le) 2/8 (Livro4 cap6)`.
- [ ] **T1.3 (3m) Re-validação 150/150 2× pós-Up:** `python scripts/verify_p6_data.py` 2× 21/21 stdout igual + `python scripts/_validate_deep.py` 150/150 2× WARNS0 BUGS0 + `docker compose config -q` RC0 + `pytest tests -q` 40 passed + `promtool check/test` 6/6 (já provado) — SWE cap14. Atualizar `reports/p6-backup.log` se pg_dump/BGSAVE vivo disponível; se offline, manter WARN documentado mas não bloqueante.
- [ ] **T1.4 (3m) T1 done gate:** `git status --porcelain` clean + `git log --oneline -3` mostra T1 commit + `git tag --list v1.0.0-p5-c` local + prova `docker ps` healthy postada em `reports/p6-hardening.log`. Commit docs/HNSW_TUNING.md §4 já tem P6-C, adicionar nota T1 hardening se preciso.

**Gate T1:** working tree clean + `docker ps` 5/5 healthy (ou 3/3 infra + api/mcp healthy) + by(le) ≥2 + 150/150 2× + 40 passed + promtool 6/6 + guard 6/6

### TRACK 2 — P7 PERF (60m, 150→158, NÃO bloqueia tag — pode ir v1.1.0 se ganho <5%)
**Refs:** HPP cap1-4 + Fluent 19-21 + Building LLM Apps evals + DDIA cap12. Axiom #1: só depois de T1 verde.

- [ ] **T2.1 (15m) Profiling hot paths:** `python -m cProfile -o reports/p7-cprofile.prof scripts/bench_hnsw.py` + snakeviz identify ToolExecutor polling sleep(2), json dumps/_to_chroma_metadata, WeakValueDictionary — HPP cap1
- [ ] **T2.2 (20m) Otimização sem regressão:** sleep(2)→event-driven ou documentar SLO; memoize json dumps; WeakValueDictionary cache; manter isolamento/cardinality/HNSW — Fluent 19-21 + HPP cap2-3 + Axiom #2
- [ ] **T2.3 (15m) Evals 6 memory types:** criar `evals/test_memory_types.py` 6 tipos episodic/semantic/procedural +3 com p95 <2× baseline — Building LLM Apps + DDIA cap12
- [ ] **T2.4 (10m) Gate 158/158:** secão W P7 8 gates em `_validate_deep.py` : cProfile exists + line_profiler + evals 6/6 + bench p95 <1.05× + cardinality <800 + guard 6/6 + verify 21/21 2× — SWE cap14

**GO/NO-GO:** se ganho <5% p95, documentar `docs/PERF_TUNING.md` e adiar para v1.1.0 — não bloqueia P8

### TRACK 3 — P8 PROD DEPLOY + DOCS (60m, 158→162, fecha v1.0.0)
**Refs:** SWE cap11-14 + DDIA cap5/6 + Livro4 cap11 + CIPHER 031/032 + ADR-001

- [ ] **T3.1 (15m) Compose prod healthy vivo (se não feito no T1):** `docker compose up -d --wait` todos healthy — healthcheck fallback já fixado
- [ ] **T3.2 (15m) IdP real + HMAC rotation + .env fail-closed:** trocar valid_ stub dev-only (JEFREY_ENV=prod deny) + ADR-001 kid v1→v2 dual-verify + validate_for_production() 8 envs ?required sem dummy — CIPHER-031/033 Axiom #3
- [ ] **T3.3 (15m) Docs finais:** SLO_RUNBOOK 1.3 + THREAT_MODEL + HNSW_TUNING §5 + CHANGELOG a partir git log bdcae44/88bf25d/687d589 + P5_CONSOLIDATION freeze — SWE cap11
- [ ] **T3.4 (15m) TAG v1.0.0 + gate 162/162:** `git tag -a v1.0.0 -m "P8 162/162"` + `git push --tags` (inclui v1.0.0-p5-c pendente D5) + secão X P8 4 gates em `_validate_deep.py` : compose healthy vivo + IdP real + CHANGELOG + tag pushado — SWE cap14 CIPHER-010

**Gate T3:** 162/162 2× + compose --wait healthy + 40 passed + guard 6/6 + verify 21/21 2× + promtool 6/6

---

## 4) ORDEM DE EXECUÇÃO — SINCRONA, SEM PARALELISMO DESINCRONIZADO

```
AGORA (pós-audit 09:40):
  1. T1.0 commit hardening (2m) → T1.1 build+up vivo (5m) → T1.2 grafana by(le) (2m) → T1.3 re-valida 150/150 2× (3m) → T1.4 gate (3m)
  => COMMIT feat(T1) + working tree clean + 150/150 2× + 40 passed + 5/5 healthy

DEPOIS (só se T1 verde):
  2. T2.1 cProfile (15m) → T2.2 otimização (20m) → T2.3 evals (15m) → T2.4 gate 158 (10m)
  => COMMIT feat(P7) 158/158 OU docs/PERF_TUNING.md se <5% (vai v1.1.0)

DEPOIS (só se T1 verde, T2 opcional):
  3. T3.1 compose prod (15m) → T3.2 IdP+HMAC (15m) → T3.3 docs (15m) → T3.4 tag 162 (15m)
  => TAG v1.0.0 + push --tags

TOTAL: T1 15m + T2 60m + T3 60m = 135m
```

Por que não paralelar T2/T3: Axiom #1 — P7 otimização, P8 deploy, ambos dependem T1 provado. Paralelizar dessincroniza gates 150→158 vs 150→162.

---

## 5) CHECKLIST QUALIDADE (toda entrega)

- [ ] `python -m py_compile $(git ls-files '*.py')` RC0
- [ ] `python -m compileall -q src` RC0
- [ ] `bash scripts/guard_anti_patterns.sh` 6/6 PASS
- [ ] `bash scripts/guard_grafana.sh` 8 panels editable false uid jefrey-main by(le) ≥1 (spec ≥2)
- [ ] `python scripts/verify_p6_data.py` 21/21 2× stdout igual RC0
- [ ] `python scripts/_validate_deep.py` 150/150 (→158/162) WARNS0 BUGS0 2×
- [ ] `docker compose config -q` RC0 (dummy prod envs se não vivo)
- [ ] `pytest tests -q` 40 passed 4 warnings + `pytest -q` 40 passed iguais
- [ ] `promtool check rules` 6 rules + `test rules` SUCCESS
- [ ] Cardinality <800, sem user_id labelnames
- [ ] Isolamento 2 tenants OK
- [ ] HNSW CONCURRENTLY AUTOCOMMIT m=16 ef=64
- [ ] Streams maxlen10000 approx + DLQ maxlen5000 + XACK + dual-verify v1/v2
- [ ] Backup pg_dump RC0 + BGSAVE ok em reports/p6-backup.log
- [ ] `git status --porcelain` vazio antes commit/tag

---

## 6) RISCOS E MITIGAÇÕES

| Risco | Mitigação | Ref |
|---|---|---|
| Quebrar isolamento em P7 | guard + test_p6_isolation 2/2 + _build_filter mandatory | Axiom #2 |
| Cardinality OOM P7 | nunca user_id labelnames; gate verify cardinality | Livro4 cap5 |
| HNSW travar | AUTOCOMMIT fixado P6-A | DDIA cap12 |
| Kid rotation quebrar | dual-verify v1/v2 + EVENTBUS_KID_LEGACY_TOTAL + DeprecationWarning | CIPHER-033 ADR-001 |
| Compose unhealthy NOAUTH | healthcheck fallback -a já no yml | DDIA cap6 |
| Falso green | 2× idempotente stdout igual + CI gate + pre-commit | SWE cap14 |
| Dessincronização | ordem estrita T1→T2→T3 + T0 contínuo | Pragmatic |
| Build timeout 300s | split build por serviço + --no-cache isolado | HPP |

---

## 7) ENTREGÁVEIS FINAIS PÓS P8

- PLANO_SINCRONIZADO_P0_P8_V2.md (este arquivo) V2.1
- scripts/_validate_deep.py 162/162 + scripts/verify_p6_data.py 21/21 2×
- reports/p6-hardening.log + p6-backup.log vivo + p7-cprofile.prof + p7-bench.log
- docs/P5_CONSOLIDATION.md freeze + HNSW_TUNING §5 + PERF_TUNING + SLO_RUNBOOK 1.3 + THREAT_MODEL + CHANGELOG
- .github/workflows/ci.yml gate 162/162 + .pre-commit-config.yaml 8 hooks
- docker-compose.yml healthy vivo + alerts.yml 6 alerts + jefrey.json 8 panels
- TAG v1.0.0 + v1.0.0-p5-c pushadas

---

## 8) COMANDOS VALIDAÇÃO (copiar-colar)

```bash
# T0 sync
git status --porcelain; python scripts/_validate_deep.py 2>&1 | tail -20
python scripts/verify_p6_data.py; python scripts/verify_p6_data.py; echo "2x OK se stdout igual"
bash scripts/guard_anti_patterns.sh; bash scripts/guard_grafana.sh; docker compose config -q && echo "compose OK"; pytest tests -q

# T1 hardening commit (PRÓXIMO)
git add Dockerfile.mcp docker-compose.yml pyproject.toml requirements.txt src/jefrey/skills/__init__.py
git commit -m "feat(T1): hardening 100% redis healthy + skill_registry + requirements sync + testpaths (Axiom #2/#4, 150/150, 40 passed)"
git status --porcelain

# T1 Up vivo (split se timeout)
docker compose build jefrey-api; docker compose build mcp-server
docker compose up -d --wait; docker ps --format "table {{.Names}}\t{{.Status}}"

# T1 grafana
python -c "import json; d=json.load(open('docker/grafana/dashboards/jefrey.json')); print([p.get('title') for p in d.get('panels',[])])"
# promtool vivo (já provado, re-run)
docker run --rm --entrypoint promtool -v "$PWD:/work" prom/prometheus:v2.53.0 check rules /work/docker/prometheus/alerts.yml
docker run --rm --entrypoint promtool -v "$PWD:/work" prom/prometheus:v2.53.0 test rules /work/docker/prometheus/tests/alerts_test.yml

# T1 re-valida
python scripts/verify_p6_data.py; python scripts/verify_p6_data.py
python scripts/_validate_deep.py 2>&1 | tail -5; pytest tests -q

# P7 perf
python -m cProfile -o reports/p7-cprofile.prof scripts/bench_hnsw.py; pytest evals/test_memory_types.py -q

# P8 tag
git tag -a v1.0.0 -m "P8 162/162 $(date -Iseconds)" && git push --tags && git log --oneline -5
```

> **Assinatura V2.1 — 2026-09-03 09:40:** Audit vivo 150/150 + 21/21 + 40 passed + promtool 6/6 + redis healthy provados. Falta só T1 commit (2m) + Up vivo api/mcp (5m) + by(le) (2m) + re-valida (3m) = 15m para 99%→100% DATA. Depois T2 60m + T3 60m = 135m até v1.0.0. Sem quebrar nada, com prova 2× idempotente.
