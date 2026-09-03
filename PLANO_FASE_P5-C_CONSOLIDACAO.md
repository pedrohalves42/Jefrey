# PLANO P5-C — CONSOLIDACAO OBSERVABILITY (close P5, 40m, 148/148, zero regressao)

> **Data:** 2026-09-02 | **Branch:** master | **Base:** 687d589 (P6-gaps 148/148) | **Slice:** 40m | **Gates:** 148/148 mantidos (P5 DONE), prepara P6-C 150/150 | **Refs:** Axiom #1-7 + 6 PRINCIPIOS FAIL-CLOSED, CIPHER-021/025/026/028/031/033/035, Livros 1,2,3 -> DURANTE P8 4,5,6 (cap5 Cardinality, cap6 Histograms, cap10 Alerting, cap11 Grafana, DDIA cap3 Persistence, SWE cap8 Style/cap14 Testing)

## 0) Objetivo

Fechar P5 sem regressao. P5.01..P5.06 ja entregues (metrics cardinality, promtool, grafana 8 panels, alerts drill 6/6, audit fallback, CI). P5-C congela, prova idempotencia e documenta. Nao avanca dado (P6-C) nem perf (P7). Sai com `148/148 100%` reproduzivel, `pytest 40 passed`, `promtool 6/6`, `verify_p6_data 19/19`, `guard 6/6`.

**P5-C != P6-C.** P5-C = observability freeze. P6-C = data verify 150/150 + CI gate + compose healthy. Se pedido "p5-c" foi typo de "p6-c", este plano deixa P5 trancado para P6-C rodar limpo em 15m.

## 1) Principios norteadores

| Principio | Regra P5-C |
|-----------|------------|
| **Axiom #1 FAIL-CLOSED** | Qualquer metrica/alert faltando = RC2, nunca degrade para stub. `guard_anti_patterns.sh` 6 greps exatos bloqueia PR. |
| **Axiom #2 ISOLAMENTO** | `user_id=None -> guest`, nunca vaza label `user_id` para Prometheus (cardinality infinita -> OOM). `labelnames=[]` ou `["tool_name","decision"]` etc, <800 series globais. |
| **Axiom #3 SEM STUB EM PROD** | `verify_p6_data.py` read-only, `drill_alerts.py` Registry direto sem mock de prod. |
| **Axiom #4 PERSISTENCIA REAL** | Grafana provisioning file-based `datasources.yml` + `dashboard.yml` com `orgId:1`, `editable:false`, `allowUiUpdates:false`. |
| **Axiom #5 CRIPTO CORRETA** | Nao toca HMAC aqui, mas valida `EVENTBUS_KID_LEGACY_TOTAL labelnames=[]` global 1 serie. |
| **Axiom #6 LEAST PRIVILEGE** | `docker-compose.yml` `.:/app:ro` + `read_only: true` + `tmpfs /tmp`, `overwrite=False`, CORS explicit sem wildcard. |
| **Axiom #7 QUALIDADE** | `py_compile` + `compileall -q src` + `ruff/mypy` via pre-commit, Sem `except: pass` silencioso (CIPHER-021). |
| **CIPHER-021** | Zero `except.*: pass` (GREP-3 exato `except.*:[[:space:]]*pass`). |
| **CIPHER-025** | Dual-write audit ja coberto em P5-05/06, P5-C apenas valida `data/audit_fallback.jsonl` redacted. |
| **CIPHER-026/028** | Rate limiting label `["tool_name","decision"]` sem `user_id`. |
| **CIPHER-033** | Kid versionado ja em P6-B, P5-C valida `EVENTBUS_KID_LEGACY_TOTAL` 1 serie. |
| **Livro4 cap5 Cardinality** | `user_id` OOM com 8M series vs 120 series com `tool_name,decision`. P5-C prova <800 via `METRICS_CARDINALITY.md`. |
| **Livro4 cap6 Histograms** | `histogram_quantile(0.95, sum(rate(..._bucket[5m])) by (le))` com `by(le)` obrigatorio (grep CI). |
| **Livro4 cap10 Alerting** | 6 alerts com `for` + `severity` + `slo` + `exp_annotations` full, `promtool test rules` 6/6. |
| **Livro4 cap11 Grafana** | 8 panels SLO, `editable:false`, `orgId:1`, `httpMethod: POST`, `path /var/lib/grafana/dashboards:ro`. |
| **DDIA cap3** | Dual-write Postgres -> jsonl fallback (P5-05). |
| **SWE cap14** | Testes isolados `pytest tests -q` 40 passed, `asyncio_mode=strict`. |

## 2) Estado atual (snapshot 687d589)

- `src/jefrey/core/metrics.py` 18 metricas, `EVENTBUS_KID_LEGACY_TOTAL labelnames=[]` 1 serie global, nenhum `user_id` em `labelnames`.
- `docker/prometheus/prometheus.yml` 26L `rule_files: /etc/prometheus/alerts.yml`.
- `docker/prometheus/alerts.yml` 67L 6 alerts (`JefreyConfigInvalid`, `JefreyApiHighErrorRate`, `JefreyRateLimitDenialsHigh`, `JefreyKidLegacyHigh`, `JefreyMemoryLatencyHigh`, `JefreyServiceDown`) com `for`/`severity`/`slo`.
- `docker/prometheus/tests/alerts_test.yml` 4.3KB 6 groups `alert_rule_test` `eval_time 4m/8m/14m`, `promtool 2.53 SUCCESS 6/6`.
- `docker/grafana/dashboards/jefrey.json` 8 panels (Config Valid, Service Up, Kid Legacy 10m, API Error Rate 5m, RateLimit Deny 5m, Memory p95, Tools Blocked 1h, Approvals HITL 1h) com `by(le)` x2, `editable:false`, `uid jefrey-main`.
- `docker/grafana/provisioning/datasources/datasources.yml` `orgId:1` `httpMethod: POST`.
- `docker/grafana/provisioning/dashboards/dashboard.yml` `editable:false` `allowUiUpdates:false` `updateIntervalSeconds:10` `path /var/lib/grafana/dashboards`.
- `scripts/drill_alerts.py` 126L Registry direto, dual `sys.path` `_ROOT/src+_ROOT`, fail-closed RC2, 6 drills.
- `scripts/drill_audit_fallback.py` 141L `tmp_path` isolado, dual `sys.path`.
- `reports/p5-04-drill.log` 4386B, `reports/p5-05-drill.log` 758B.
- `tests/test_p5_alerts_drill.py` 66L 4 tests, `tests/test_p5_audit_fallback.py` 88L 3 tests, `tests/test_p5_grafana_dashboards.py` 63L, `tests/test_p5_metrics_cardinality.py` 126L.
- `docs/METRICS_CARDINALITY.md` 70L prova <800 series, `SLO_RUNBOOK.md` Appendix P5-04, `THREAT_MODEL.md` + `ADR-001`.
- `docker-compose.yml` 244L `postgres pgvector ankane/pgvector:latest` `redis 7.2 requirepass` `prometheus 2.53.0` `grafana 11.1.0` com `:ro` + `read_only` + `tmpfs`.
- `.github/workflows/ci.yml` guard 6 greps + `audit prod` + `pytest` + `promtool` + `REGISTRY no user_id` + `compose config -q`.
- `.pre-commit-config.yaml` `guard` + `ruff/mypy` + `metrics-no-user-id` + `promtool` + `grafana-lint` via `scripts/guard_grafana.sh`.
- Gates atuais: `py_compile 3/3 OK`, `compileall RC0`, `guard 6/6 PASS`, `json.tool OK`, `yaml 8/8 OK`, `cardinality [] OK`, `verify_p6_data 19/19 100% idempotente 2x`, `deep 148/148 100%`, `pytest 40 passed` (38+2 isolation), `reports 4 exists`.

## 3) Escopo P5-C (o que entra / o que NAO entra)

**ENTRA (freeze):**
- Re-auditar P5.01..P5.06 sem mudar semantica, apenas consertar doc/comentario se faltar.
- Congelar `metrics.py` labelnames, `alerts.yml` 6 rules, `jefrey.json` 8 panels, `datasources.yml`/`dashboard.yml`, `drill_*` idempotentes.
- Adicionar `docs/P5_CONSOLIDATION.md` 60-80L com matriz 6 alerts x PromQL x for x slo x runbook.
- Garantir `verify_p5.py` (se existir) ou `scripts/_validate_deep.py` secao P5 ja cobre tudo; se faltar, adicionar secao `P5-C` +2 gates (idempotencia drill).
- `git tag v1.0.0-p5-c` local (nao push) como checkpoint antes de P6-C.

**NAO ENTRA (fica para P6-C/P7/P8):**
- Nenhum `CREATE INDEX CONCURRENTLY`, `HNSW`, `bench_hnsw`, `pgvector` tuning (P6-A DONE).
- Nenhum `XADD/XREADGROUP/DLQ/kid rotation` (P6-B DONE).
- Nenhum `cProfile/line_profiler` (P7).
- Nenhum `docker compose up -d --wait healthy` com IdP real nem push de tag (P8).

## 4) Subtarefas (40m total, 5 blocos)

### C1 — Audit P5 diff vs spec (5m)

Verifica que `P5.01..P5.06` batem com `PLANO_FASE_P5-*.md`. Roda `scripts/_validate_deep.py` e `scripts/verify_p5.py` (se existir) e compara gates.

ERRADO (esquecer):
```python
# _validate_deep.py sem secao P5-C, fica 148/148 mas sem prova de idempotencia drill
```

CORRETO:
```python
# secao P5-C: drill_alerts idempotente 2x RC0 + drill_audit_fallback 2x RC0
if drill_alerts_idempotente and drill_audit_idempotente: oks.append("P5-C drills idempotentes 2x")
```

Gate: `148/148` mantido, nenhum `WARN`.

### C2 — Metrics cardinality freeze (10m, Livro4 cap5, Axiom #2)

Congela `src/jefrey/core/metrics.py` 18 metricas, nenhuma com `user_id`. Prova `<800 series` via `docs/METRICS_CARDINALITY.md`.

ERRADO (regressao cardinalidade):
```python
RATE_LIMIT_TOTAL = Counter("jefrey_rate_limit_total", labelnames=["user_id", "tool_name"])  # OOM 8M series
```

CORRETO (freeze):
```python
RATE_LIMIT_TOTAL = Counter("jefrey_rate_limit_total", labelnames=["tool_name", "decision"])  # ~120 series
EVENTBUS_KID_LEGACY_TOTAL = Counter("jefrey_eventbus_kid_legacy_total", labelnames=[])  # 1 serie global
# grep labelnames.*user_id deve ser 0, exceto comentario "never user_id"
```

Validacao:
```bash
python -c "import re,pathlib; t=pathlib.Path('src/jefrey/core/metrics.py').read_text(); assert 'labelnames=[]' in t; assert t.count('user_id')==1"  # so comentario
python -c "import pathlib; print(pathlib.Path('docs/METRICS_CARDINALITY.md').stat().st_size)"
```

### C3 — Grafana 8 panels freeze (10m, Livro4 cap6/11, Axiom #4)

Trava `jefrey.json` 8 panels SLO + provisioning. Valida `by(le)` x2, `editable:false`, `orgId:1`, `:ro`.

ERRADO (regressao Grafana):
```json
{"editable": true, "panels": [{"targets": [{"expr": "histogram_quantile(0.95, rate(jefrey_memory_latency_seconds_bucket[5m]))"}]}]}
```

CORRETO:
```json
{"editable": false, "uid": "jefrey-main", "panels": [{"targets": [{"expr": "histogram_quantile(0.95, sum(rate(jefrey_memory_latency_seconds_bucket[5m])) by (le))"}]}]}
```
```yaml
# datasources.yml
orgId: 1
jsonData: {httpMethod: POST}
# dashboard.yml
editable: false
allowUiUpdates: false
updateIntervalSeconds: 10
path: /var/lib/grafana/dashboards
```

Validacao:
```bash
python -m json.tool docker/grafana/dashboards/jefrey.json > /dev/null && echo JSON_OK
python -c "import json,pathlib; d=json.loads(pathlib.Path('docker/grafana/dashboards/jefrey.json').read_text()); assert len(d['panels'])==8; assert d['editable'] is False; assert sum('by (le)' in json.dumps(p) for p in d['panels'])>=2"
bash scripts/guard_grafana.sh  # json.tool + yaml safe_load + !grep user_id + grep by(le) + editable false + orgId
```

### C4 — Alerts 6/6 + drill idempotente + runbook (10m, Livro4 cap10)

Congela `alerts.yml` 6 rules + `alerts_test.yml` 6 groups + `drill_alerts.py` idempotente 2x + `SLO_RUNBOOK.md` Appendix.

ERRADO (alert sem for/severity):
```yaml
- alert: JefreyServiceDown
  expr: up == 0
```

CORRETO:
```yaml
- alert: JefreyServiceDown
  expr: up{job="jefrey-api"} == 0
  for: 1m
  labels: {severity: critical, slo: availability}
  annotations: {summary: "jefrey-api down", description: "Up==0 ha 1m - checar docker logs jefrey-api, health /health, postgres/redis health."}
```

Idempotencia drill:
```bash
python scripts/drill_alerts.py; echo RC:$?  # RC0
python scripts/drill_alerts.py; echo RC:$?  # RC0 de novo
python scripts/drill_audit_fallback.py; echo RC:$?
python scripts/drill_audit_fallback.py; echo RC:$?
promtool test rules docker/prometheus/tests/alerts_test.yml  # SUCCESS 6/6
promtool check rules docker/prometheus/alerts.yml  # SUCCESS
```

### C5 — Re-validacao full + commit P5-C (5m, SWE cap14)

Roda suite completa e commita unico `feat(P5-C): consolidacao observability freeze 148/148`.

Suite P5-C (ordem fixa, fail-closed):
```bash
python -m py_compile scripts/drill_alerts.py scripts/drill_audit_fallback.py scripts/verify_p6_data.py
python -m compileall -q src
bash scripts/guard_anti_patterns.sh  # 6/6 PASS exato
bash scripts/guard_grafana.sh
python -m json.tool docker/grafana/dashboards/jefrey.json > /dev/null
python -c "import yaml,pathlib; [yaml.safe_load(pathlib.Path(p).read_text()) for p in ['docker-compose.yml','.pre-commit-config.yaml','docker/prometheus/prometheus.yml','docker/prometheus/alerts.yml']]"
python -c "import re,pathlib; assert not re.search(r'labelnames.*user_id', pathlib.Path('src/jefrey/core/metrics.py').read_text())"
python scripts/verify_p6_data.py  # 19/19 100%
python scripts/verify_p6_data.py  # idempotente 2x
python scripts/_validate_deep.py  # 148/148 100% WARNS0 BUGS0
python -m pytest tests -q  # 40 passed (38+2 isolation, 5 com kid)
promtool check rules docker/prometheus/alerts.yml
promtool test rules docker/prometheus/tests/alerts_test.yml  # 6/6
docker compose config -q  # com envs dummy prod (JEFREY_EVENTBUS__HMAC_KEYS_JSON etc)
```

Commit:
```bash
git add -A
git commit -m "feat(P5-C): consolidacao observability freeze 148/148 idempotente (Livro4 cap5/6/10/11, DDIA cap3, SWE cap14, Axiom #2/#4, CIPHER-021)"
git tag v1.0.0-p5-c  # local, nao push
```

Gera `docs/P5_CONSOLIDATION.md` 60-80L com matriz 6 alerts x PromQL x for x slo x runbook link.

## 5) Gates P5-C (148/148 mantidos, zero regressao)

| Gate | Prova | Comando |
|------|-------|---------|
| py_compile 3/3 | drill_alerts, drill_audit, verify_p6_data | `python -m py_compile ...` RC0 |
| compileall | src sem SyntaxError | `python -m compileall -q src` RC0 |
| guard 6/6 | exatos `dev-auto-generated-key`, `return "allow"`, `except.*: pass`, `str(dict)`, `b64encode sem urlsafe`, `overwrite=True/:-jefrey/.:/app sem :ro` | `bash scripts/guard_anti_patterns.sh` 6 PASS |
| grafana lint | 8 panels, by(le) x2, editable false, orgId 1 | `bash scripts/guard_grafana.sh` RC0 |
| yaml 8/8 | compose, pre-commit, prometheus, alerts | `yaml.safe_load` 8 OK |
| cardinality | 0 `labelnames.*user_id`, `labelnames=[]` bracket | `grep labelnames` 0 hits |
| cardinality doc | <800 series | `docs/METRICS_CARDINALITY.md` exists |
| alerts 6/6 | promtool 2.53 | `promtool test rules` SUCCESS 6/6 |
| drills idempotentes | 2x RC0 | `drill_alerts.py` 2x + `drill_audit_fallback.py` 2x |
| verify_p6_data | 19/19 100% 2x | `python scripts/verify_p6_data.py` 2x |
| deep | 148/148 100% WARNS0 BUGS0 | `python scripts/_validate_deep.py` |
| pytest | 40 passed | `python -m pytest tests -q` |
| compose | config -q com envs dummy prod | `docker compose config -q` RC0 |
| reports | 4 exists | `ls reports/p6-*.log` 4 files |
| git | working tree clean exceto tag local | `git status -sb` clean |

## 6) Riscos e mitigacoes

| Risco | Mitigacao |
|-------|-----------|
| Regressao cardinality por novo label `user_id` | CI `REGISTRY no user_id` + `guard` + `METRICS_CARDINALITY.md` <800, fail-closed RC2 |
| Grafana editable true volta | `guard_grafana.sh` grep `editable.*false` + `json.tool` |
| PromQL sem `by(le)` | CI grep `by \(le\)` >=2, `guard_grafana.sh` |
| Drill nao idempotente (estado sujo) | `drill_*` com `Registry()` isolado + `tmp_path`, roda 2x na suite |
| `except: pass` silencioso | GREP-3 exato `except.*:[[:space:]]*pass` no `guard_anti_patterns.sh` |
| `.:/app` sem `:ro` | GREP-6c `overwrite=True|In-memory|:-jefrey|.:/app without :ro` exato |
| Tag p5-c conflita com p6-c | Tag local `v1.0.0-p5-c` nao push, P6-C usa `v1.0.0-p6-c` depois |

## 7) Entregaveis P5-C

- `docs/P5_CONSOLIDATION.md` 60-80L (matriz 6 alerts x PromQL x for x slo x runbook + 8 panels map + cardinality <800).
- `scripts/_validate_deep.py` secao P5-C +2 gates se faltar (opcional, se ja 148/148 pode so documentar).
- `reports/` inalterados (4 logs), `git tag v1.0.0-p5-c` local.
- Commit unico `feat(P5-C): ... 148/148` com `git status` clean.

## 8) Validacao final P5-C (copiar e colar, ordem fixa)

```bash
python -m py_compile scripts/drill_alerts.py scripts/drill_audit_fallback.py scripts/verify_p6_data.py && echo PY_COMPILE_OK
python -m compileall -q src && echo COMPILEALL_OK
bash scripts/guard_anti_patterns.sh && echo GUARD_OK
bash scripts/guard_grafana.sh && echo GRAFANA_OK
python -m json.tool docker/grafana/dashboards/jefrey.json > /dev/null && echo JSON_OK
python -c "import yaml,pathlib; [yaml.safe_load(pathlib.Path(p).read_text(encoding='utf-8')) for p in ['docker-compose.yml','.pre-commit-config.yaml','docker/prometheus/prometheus.yml','docker/prometheus/alerts.yml','docker/grafana/provisioning/datasources/datasources.yml','docker/grafana/provisioning/dashboards/dashboard.yml']]; print('YAML_OK 6/6')"
python -c "import re,pathlib; t=pathlib.Path('src/jefrey/core/metrics.py').read_text(encoding='utf-8'); print('CARDINALITY_OK' if not re.search(r'labelnames.*user_id', t) and 'labelnames=[]' in t else 'CARDINALITY_FAIL')"
python scripts/verify_p6_data.py && python scripts/verify_p6_data.py && echo VERIFY_IDEMPOTENTE_OK
python scripts/_validate_deep.py
python -m pytest tests -q
promtool check rules docker/prometheus/alerts.yml && echo PROMTOOL_CHECK_OK
promtool test rules docker/prometheus/tests/alerts_test.yml && echo PROMTOOL_TEST_6/6_OK
docker compose config -q && echo COMPOSE_OK
ls -lh reports/p6-hnsw-proof.log reports/p6-bench.log reports/p6-streams.log reports/p6-backup.log
git status -sb
```

Esperado: `148/148 100% WARNS0 BUGS0`, `40 passed`, `6/6 SUCCESS`, `19/19 100% 2x`, `COMPOSE_OK`, `clean`.

## 9) Proximos passos apos P5-C

- **P6-C (15m, 148->150):** `verify_p6_data` 19->21 (+ backup/restore idempotente), `_validate_deep` 148->150 (+2 gates backup), CI gate `verify_p6_data` no `ci.yml`, `pre-commit` hook `verify_p6_data`, `docker compose up -d --wait healthy` fix `jefrey-api/mcp Restarting(1)` + `redis unhealthy NOAUTH` via `redis-cli -a $PASSWORD`, `docs/HNSW_TUNING.md` § final.
- **P7 PERF (60m, 150->158):** DEPOIS de P6 estavel, HPP/Fluent, `cProfile` + `line_profiler` hot paths `ToolExecutor polling sleep(2)` + `json dumps` + `WeakValueDictionary`, Axiom #1 proibe otimizacao prematura.
- **P8 TAG (60m, 158->162):** `tag v1.0.0`, `CHANGELOG` desde `687d589`, `docker compose up -d --wait healthy` + IdP real (fora de `valid_` stub) + `ADR-001` kid rotation + `SLO_RUNBOOK 1.3` + `.env dummy ?required`.

---
**Checklist de aceite P5-C (tudo deve ser SIM):**
- [ ] `148/148` reproduzivel 2x sem WARN/BUG?
- [ ] `guard 6/6 PASS` exato (nao regex ampla)?
- [ ] `cardinality` 0 `user_id` em `labelnames`, `EVENTBUS_KID_LEGACY_TOTAL []` 1 serie?
- [ ] `grafana` 8 panels `by(le) x2` `editable:false` `orgId:1` `:ro`?
- [ ] `alerts` 6/6 `for`+`severity`+`slo`+`exp_annotations` + `promtool 6/6`?
- [ ] `drills` idempotentes 2x RC0?
- [ ] `pytest 40 passed`?
- [ ] `docs/P5_CONSOLIDATION.md` 60-80L com matriz?
- [ ] `git tag v1.0.0-p5-c` local e `status clean`?
Se qualquer NAO -> nao avanca para P6-C.
