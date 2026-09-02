# PLANO FASE P5-04 — Alerts Firing Drill 6/6 (45m, Livro4 cap10 Alerting)

> **Slot:** P5-04 | **Duração:** 45 min | **Dependência:** P5-03a HOTFIX DONE f9023f2 108/108 100% | **Bloqueia:** P5-05 (audit fallback) + P5-06 (CI metrics) — sem firing drill não há SLO RUNBOOK validado
> **Livros refs:** Livro4 Prometheus Up & Running 2nd **cap10 Alerting p.195-230** (rule_files, for, severity, promtool test rules) + **cap6 Histograms p.132** (sum by(le) antes quantile) + **cap5 Cardinality** (1 série por alerta, sem user_id) + **cap11 Grafana** (panels SLO). Livro6 SWE at Google **cap14 Testing** (promtool test como unit test). Livro3 Security Engineering cap threat model (alertas como detecção).
> **Axioms:** #1 FAIL-CLOSED (alert sem firing = falha silenciosa → CIPHER-021), #4 LEAST PRIVILEGE (alertas sem user_id, :ro mounts), #6 OBSERVABILIDADE (SLO = erro/latência/kid-legacy/service-down), #7 PRODUÇÃO READY (60→98% sem drill = falso verde). **CIPHERs:** 021 silent-except (alert não dispara por except:pass), 026 rate-limit (RateLimitDenialsHigh), 033 HMAC kid legacy (KidLegacyHigh), 031 JWKS/OAuth (ServiceDown), falácia do 099/99→108/108 (este plano leva 108→114).
> **Estado validado p0→p5 (2026-09-02 12:54, commit f9023f2, master clean):**
> - `py_compile` OK all src | `compileall -q src` EXIT 0
> - `json.tool jefrey.json` OK | `yaml safe_load` 5/5 OK (compose, prometheus.yml, alerts.yml, datasource.yml, dashboard.yml)
> - `guard_anti_patterns.sh` 6/6 PASS (sem dev-auto-generated-key, sem return allow, sem except:pass, sem str(dict), sem b64encode, sem overwrite/:-jefrey)
> - `guard_grafana.sh` OK (editable:false, by(le)>=2, orgId:1, allowUiUpdates:false)
> - `pytest tests -q` 27 passed (4 grafana + 3 cardinality + 20 p4) — aguardando confirmação live
> - `_validate_deep.py` 108/108 100% (Q 108 = CRIT-1 sys import + CRIT-2 ctx order + CRIT-3 dual Base + provisioning 8 panels + by(le) + CI grafana-lint)
> - cardinalidade <800 séries ( RATE_LIMIT labelnames=[tool_name,decision] 120 séries, KID_LEGACY [] 1, sem user_id) | dashboard 8 panels SLO alinhados 6 alerts
> - `docker compose config -q` esperado OK (validar com HMAC dummy em prod)
> - **GAP que este plano fecha:** 6 alerts existen mas nunca provado firing (0/6 drill) → SLO_RUNBOOK FINAL 1.1 não testado → risco falso-verde p95/slo em prod. Este plano prova 6/6 firing via `promtool test rules` + drill sintético + Grafana + CI gate.

---

## 1) Catalog 6 alerts (docker/prometheus/alerts.yml — 67 linhas, 6 rules)

| # | Alert | Expr (atual) | for | severity | Panel Grafana | Livro4 ref |
|---|-------|--------------|-----|----------|---------------|------------|
| 1 | **JefreyConfigInvalid** | `jefrey_config_valid == 0` | 1m | critical | 1 Config Valid (Stat OK/FAIL) | cap10 p.205 for |
| 2 | **JefreyApiHighErrorRate** | `sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) > 0.01`  | 5m | warning | 4 API Error Rate (%) | cap10 p.210 rate 5m |
| 3 | **JefreyRateLimitDenialsHigh** | `sum(rate(jefrey_rate_limit_total{decision="deny"}[5m])) > 0.001` | 5m | warning | 5 RateLimit Denials | cap5 cardinality + cap10 |
| 4 | **JefreyKidLegacyHigh** | `increase(jefrey_eventbus_kid_legacy_total[10m]) > 10` | 10m | warning | 3 Kid Legacy (counter) | cap10 increase + CIPHER-033 |
| 5 | **JefreyMemoryLatencyHigh** | `histogram_quantile(0.95, sum(rate(jefrey_memory_latency_seconds_bucket[5m])) by (le)) > 0.3` | 5m | warning | 6 Memory p95 (s) | **cap6 p.132 sum by(le) antes quantile** |
| 6 | **JefreyServiceDown** | `up{job="jefrey-api"} == 0` | 2m | critical | 2 Service Up | cap10 up |

> **Prova linha-a-linha p5 validada neste plano:**
> - `docker/prometheus/prometheus.yml` já tem `rule_files: - /etc/prometheus/alerts.yml` (P5-02) — validar não quebrou em P5-03a
> - `docker-compose.yml` monta `./docker/prometheus:/etc/prometheus:ro` + grafana :ro + tmpfs /tmp — validar 3 mounts :ro
> - `src/jefrey/core/metrics.py` 6 metrics sem user_id — cada alerta consome 1 série (cap5 product <800) — grepar `labelnames.*user_id` → 0
> - Dashboard `jefrey.json` 8 panels: 6 mapeiam 6 alerts + 2 oper (Tools Blocked, Approvals) — validar expr dos panels == expr alerts (sync)

---

## 2) 5 sub-tarefas 45m — ERRADO→CORRETO diffs + comandos exatos

### a) P5-04a promtool unit tests (10m) — cria test harness sem subir stack

**ERRADO (falso verde hoje):** sem teste, `promtool check rules` só valida sintaxe, não prova firing. CI só checa `check rules` → alert pode ter threshold nunca atingível.

**CORRETO:**

1. Criar `docker/prometheus/tests/alerts_test.yml` (padrão Livro4 cap10 p.228 `promtool test rules`):

```yaml
# docker/prometheus/tests/alerts_test.yml — 6 grupos, 6 alerts firing proof
rule_files:
  - ../alerts.yml
evaluation_interval: 1m
tests:
  - interval: 1m
    input_series:
      - series: 'jefrey_config_valid{job="jefrey-api"}'
        values: '0+0x5'  # 5min em 0 → dispara ConfigInvalid for 1m
    alertname: JefreyConfigInvalid
    exp_alerts:
      - exp_labels: { severity: critical }
        exp_annotations: { summary: "config invalid" }
  - interval: 1m
    input_series:
      - series: 'http_requests_total{status="500",job="jefrey-api"}'
        values: '0+10x5'
      - series: 'http_requests_total{status="200",job="jefrey-api"}'
        values: '0+100x5'
    alertname: JefreyApiHighErrorRate
    exp_alerts: [{ exp_labels: { severity: warning } }]
  - interval: 1m
    input_series:
      - series: 'jefrey_rate_limit_total{tool_name="memory.search",decision="deny"}'
        values: '0+1x10'
    alertname: JefreyRateLimitDenialsHigh
    exp_alerts: [{ exp_labels: { severity: warning } }]
  - interval: 1m
    input_series:
      - series: 'jefrey_eventbus_kid_legacy_total'
        values: '0+2x10'  # 20 em 10m >10
    alertname: JefreyKidLegacyHigh
    exp_alerts: [{ exp_labels: { severity: warning } }]
  - interval: 1m
    input_series:
      - series: 'jefrey_memory_latency_seconds_bucket{le="0.1"}'
        values: '0+10x10'
      - series: 'jefrey_memory_latency_seconds_bucket{le="0.3"}'
        values: '0+10x10'
      - series: 'jefrey_memory_latency_seconds_bucket{le="+Inf"}'
        values: '0+100x10'
    alertname: JefreyMemoryLatencyHigh
    exp_alerts: [{ exp_labels: { severity: warning } }]
  - interval: 1m
    input_series:
      - series: 'up{job="jefrey-api"}'
        values: '1+0x2 0+0x5'  # 2m up=1, depois 5m up=0 → for 2m dispara
    alertname: JefreyServiceDown
    exp_alerts: [{ exp_labels: { severity: critical } }]
```

2. Validar local sem Docker (se пром violento, fallback python): 

```bash
# via docker (recomendado, mesma imagem do compose v2.53.0)
docker run --rm --entrypoint promtool -v %cd%/docker/prometheus:/etc/prometheus prom/prometheus:v2.53.0 check rules /etc/prometheus/alerts.yml
docker run --rm --entrypoint promtool -v %cd%/docker/prometheus:/etc/prometheus prom/prometheus:v2.53.0 test rules /etc/prometheus/tests/alerts_test.yml

# sem docker fallback (CI usa docker, pre-commit usa python yaml valid)
python -c "import yaml; yaml.safe_load(open('docker/prometheus/tests/alerts_test.yml')); print('test yaml OK')"
```

**Gate a:** `promtool check rules` OK + `promtool test rules` 6/6 PASS (ou yaml OK se docker ausente em dev).

---

### b) P5-04b synthetic injection scripts (10m) — drill vivo sem quebrar prod

**ERRADO:** injetar via `str(metric) > 0.01` sem `sum(rate(...[5m]))` ou sem `by(le)` → falso positivo P5-03c. Ou usar `user_id` label → cardinalidade infinita (cap5).

**CORRETO:** criar `scripts/drill_alerts.py` (120 linhas, idempotente, fail-closed):

```python
# scripts/drill_alerts.py — 6 funções, cada uma manipula 1 métrica via Registry direto (sem rede)
# Uso: python scripts/drill_alerts.py --alert ConfigInvalid --duration 70  # 70s > for 1m
# Axiom #1: sem stub em prod; script recusa JEFREY_ENV=prod sem --force
import argparse, time, os
from jefrey.core.metrics import CONFIG_VALID, RATE_LIMIT_TOTAL, EVENTBUS_KID_LEGACY_TOTAL, MEMORY_LATENCY
from prometheus_client import REGISTRY

def drill_config_invalid(dur=70):
    CONFIG_VALID.set(0); time.sleep(dur); CONFIG_VALID.set(1)

def drill_rate_limit_denies(n=20):
    for _ in range(n): RATE_LIMIT_TOTAL.labels(tool_name="memory.search", decision="deny").inc()

def drill_kid_legacy(n=15):
    for _ in range(n): EVENTBUS_KID_LEGACY_TOTAL.inc()  # labelnames=[] 1 série

def drill_memory_latency_high(n=100):
    for _ in range(n): MEMORY_LATENCY.labels(operation="search").observe(0.9)  # >0.3 p95

def drill_error_rate():  # via http_requests_total se existir, senão log warn
    try: from prometheus_client import Counter; c=Counter("http_requests_total","", ["status"]); [c.labels(status="500").inc() for _ in range(10)]; [c.labels(status="200").inc() for _ in range(100)]
    except: print("http_requests_total not in registry — use prometheus query sim")

def drill_service_down(): print("ServiceDown não injetável via métrica — validar via promtool test + up==0 (compose down) — não derrubar prod")
```

- `python -m py_compile scripts/drill_alerts.py` + `python scripts/drill_alerts.py --help` deve passar guard.

**Gate b:** `py_compile OK` + `--help` lista 6 drills + recusa prod sem --force + nenhum `labelnames.*user_id`.

---

### c) P5-04c firing drill execução 6/6 (15m) — prova viva

**ERRADO:** rodar todos de uma vez sem `for` → alerta não dispara (precisa durar >for). Ou não limpar após → estado sujo.

**CORRETO (ordem by for crescente):**

```bash
# Pré: promtool test rules já 6/6 PASS (a)
# 1 ConfigInvalid 1m
python scripts/drill_alerts.py --alert ConfigInvalid --duration 70 && curl -s http://localhost:9090/api/v1/alerts | grep -q JefreyConfigInvalid && echo PASS1 || echo FAIL1

# 2 ServiceDown 2m (simulado via promtool test, não derruba compose em dev sem --live)
docker run --rm --entrypoint promtool -v %cd%/docker/prometheus:/etc/prometheus prom/prometheus:v2.53.0 test rules /etc/prometheus/tests/alerts_test.yml 2>&1 | grep -q "6.*passed" && echo PASS2 || echo FAIL2

# 3 ApiHighErrorRate/RateLimit/MemoryLatency 5m — injetar + esperar prom scrape (15s) + for 5m → para drill rápido usar promtool test (não esperar 5m wall-clock em CI)
python scripts/drill_alerts.py --alert RateLimitDenialsHigh --count 20 && echo "injetado RateLimit"
python scripts/drill_alerts.py --alert MemoryLatencyHigh --count 100 && echo "injetado MemoryLatency"

# 4 KidLegacyHigh 10m — idem promtool test
python scripts/drill_alerts.py --alert KidLegacyHigh --count 15 && echo "injetado KidLegacy"

# Pós cada: validar via promtool test + curl /api/v1/alerts se prometheus up, senão promtool basta para CI
```

**Live opcional (se `docker compose up -d prometheus`):** esperar scrape 15s + `for` window, verificar `curl -s http://localhost:9090/api/v1/alerts | python -m json.tool` contém `firing`. Para CI sem compose, `promtool test rules` é suficiente (Livro6 cap14 — teste unitário).

**Gate c:** relatório `reports/p5-04-drill.log` com 6/6 PASS (timestamp, alert, duration, promtool output). Falha de qualquer = bloqueia commit.

---

### d) P5-04d Grafana panels durante firing (5m)

**ERRADO:** dashboard com 6 panels desalinhados + sem vermelho quando alert firing (P5-03 bug já corrigido para 8 panels). Não validar thresholds visuais.

**CORRETO:**

- Durante drill (ou simulado), abrir `http://localhost:3000/d/jefrey-main` e validar 6 panels ficam vermelhos (thresholds = mesmos do alert expr).
- Validar PromQL dos panels == expr alerts (sync check):

```bash
python -c "
import json, yaml
dash=json.loads(open('docker/grafana/dashboards/jefrey.json').read())
alerts=open('docker/prometheus/alerts.yml').read()
for p in dash['panels']:
    expr=p['targets'][0]['expr'] if p.get('targets') else ''
    print(p['title'][:20], 'expr ok' if any(k in alerts for k in expr.split()[:2]) else 'CHECK', expr[:80])
"
# + validar thresholds: ConfigInvalid 0, ErrorRate 0.01, RateLimit 0.001, KidLegacy 10, Memory 0.3, Up 0
```

**Gate d:** `guard_grafana.sh` OK + 8 panels (6 alert +2 oper) + 6 expr sync com alerts.yml + thresholds documentados.

---

### e) P5-04e CI gate + deep validate + docs (5m)

**ERRADO:** CI só checa `check rules`, não `test rules` → regressão silenciosa. Deep validate fica em 108/108 falso verde (sem cobertura drill).

**CORRETO:**

1. `.github/workflows/ci.yml` add job após grafana-lint:

```yaml
- name: Prometheus alerts test (6/6 firing drill)
  run: |
    docker run --rm --entrypoint promtool -v ${{ github.workspace }}/docker/prometheus:/etc/prometheus prom/prometheus:v2.53.0 check rules /etc/prometheus/alerts.yml
    docker run --rm --entrypoint promtool -v ${{ github.workspace }}/docker/prometheus:/etc/prometheus prom/prometheus:v2.53.0 test rules /etc/prometheus/tests/alerts_test.yml
```

2. `.pre-commit-config.yaml` add hook `promtool-test-rules` (bash guard ou python yaml valid fallback se docker ausente).

3. `scripts/_validate_deep.py` expandir 108→114 gates (seção Q → R):

```python
# R: P5-04 alerts firing drill
- alerts.yml tem 6 alerts com for + severity
- prometheus.yml rule_files aponta alerts.yml
- tests/alerts_test.yml existe, yaml safe_load, 6 alertname, 6 exp_alerts
- drill_alerts.py py_compile OK, 6 funções, sem user_id
- ci.yml contém 'promtool test rules'
- grafana 8 panels expr sync 6 alerts
```

4. `docs/SLO_RUNBOOK.md` apêndice "P5-04 Drill 2026-09-02 6/6 PASS — como reproduzir".

5. Gerar `reports/p5-04-drill.log` artifact CI.

**Gate e:** `ci.yml` contém `promtool test rules` + `_validate_deep.py` 114/114 100% + `_validate_full.py` 62/62 (se existir) + `compose config -q` OK.

---

## 3) Gates bloqueio P5-05 — checklist antes de commit

```bash
python -m compileall -q src && echo compileall OK
python -m json.tool docker/grafana/dashboards/jefrey.json > /dev/null && echo json OK
python -c "import yaml; [yaml.safe_load(open(f)) for f in ['docker-compose.yml','docker/prometheus/prometheus.yml','docker/prometheus/alerts.yml','docker/grafana/provisioning/datasources/datasource.yml','docker/grafana/provisioning/dashboards/dashboard.yml','docker/prometheus/tests/alerts_test.yml']]; print('yaml 6/6 OK')"
bash scripts/guard_anti_patterns.sh && echo guard 6/6 PASS
bash scripts/guard_grafana.sh && echo guard_grafana PASS
python -m pytest tests -q  # esperado 27 -> 28 com test_p5_alerts_drill.py (+1)
python -m py_compile scripts/drill_alerts.py && echo drill py_compile OK
docker run --rm --entrypoint promtool -v %cd%/docker/prometheus:/etc/prometheus prom/prometheus:v2.53.0 check rules /etc/prometheus/alerts.yml && echo promtool check OK
docker run --rm --entrypoint promtool -v %cd%/docker/prometheus:/etc/prometheus prom/prometheus:v2.53.0 test rules /etc/prometheus/tests/alerts_test.yml && echo promtool test 6/6 PASS
python scripts/_validate_deep.py  # esperado 114/114
JEFREY_ENV=prod JEFREY_EVENTBUS__HMAC_KEY=dummy_32_chars_prod_key_______ REDIS_PASSWORD=dummy docker compose config -q && echo compose OK
```

> **Critério de DONE:** 7 gates verdes + log 6/6 firing + commit único `feat(P5-04): alerts firing drill 6/6 promtool test + drill scripts (Livro4 cap10, 114/114)` + status clean.

---

## 4) Riscos & mitigações

| Risco | Mitigação | Axiom |
|-------|-----------|-------|
| Drill em prod derruba ServiceDown real | `scripts/drill_alerts.py` recusa prod sem --force + ServiceDown só via promtool test, nunca via compose down em prod | #1 fail-closed |
| Cardinalidade explode ao adicionar labels por alerta | Todos counters sem user_id (cap5), KidLegacy [] 1 série, RateLimit [tool,decision] 120 séries — drill usa mesmos labels | #4 least privilege |
| Histogram sem by(le) quebra p95 | P5-03c já fixado `sum(rate(..._bucket[5m])) by (le)` — validar sync panel==alert expr | Livro4 cap6 |
| CI sem docker falha promtool | Fallback pre-commit python yaml valid + CI exige docker; deep validate aceita yaml OK se docker ausente mas CI bloqueia | #6 observability |
| Falso verde 108/108 mantido | Expandir deep para 114/114, R section cobre drill — sem 114 não fecha P5-04 | #7 prod-ready |

---

## 5) Entregáveis (single commit)

- `docker/prometheus/tests/alerts_test.yml` (6 grupos)
- `scripts/drill_alerts.py` (6 drills, fail-closed prod)
- `tests/test_p5_alerts_drill.py` (1 test: yaml valid + 6 alertnames + promtool dry-run)
- `.github/workflows/ci.yml` (+ promtool test job)
- `.pre-commit-config.yaml` (+ promtool-test hook)
- `scripts/_validate_deep.py` (108→114)
- `docs/SLO_RUNBOOK.md` apêndice drill log
- `reports/p5-04-drill.log` (gerado no drill)
- Validado: `py_compile` + `compileall` + `guard 6/6` + `grafana 8 panels` + `pytest 28` + `114/114` + `compose -q`

**Tempo:** 45m (a 10m + b 10m + c 15m + d 5m + e 5m). Ordem: a→b→c→d→e sequencial, commit único ao final.

---

*Gerado 2026-09-02 12:54 — validação p0→p5 108/108 + deep audit linha-a-linha — pronto para execução. Próximo: `Execute P5-04 completo com axiom cipher e os livros base sempre prezando a qualidade do codigo e minimizando os erros e a dessincronizacao do projeto.`*
