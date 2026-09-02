# PLANO FASE P5-03 — Grafana Dashboard (40 min)

**Versão:** 1.0 — 2026-09-02 — P5-03 Grafana Dashboard Provisionado
**Base:** P5-02 DONE `4d6387b` 95/95 gates 100% + `docker-compose.yml` (prometheus+grafana 6 alerts) + `docker/grafana/*` existente (3 arquivos, 6 painéis desalinhados) + `docs/METRICS_CARDINALITY.md` 13 métricas <800 séries
**Stack alvo:** `grafana/grafana:11.1.0` + `prom/prometheus:v2.53.0` + `jefrey-api:8000/metrics` — `30d retention` + `rule_files /etc/prometheus/alerts.yml` (P5-02)
**SLO:** P5-Observability 3 h → P5-03 40 min (Livro 4 cap.11 Grafana, Axiom #1 Fail-Closed + #4 Least Privilege + #7 Observability, CIPHER-010 Audit/Observabilidade + 021 Silent Except + 026 Rate-Limit label)

---

## 1. OBJETIVO (por que este slice existe)

Entregar **Grafana provisionado por código** (datasource + dashboard JSON) — sem clique manual — com **8 painéis SLO-alinhados** aos 6 alerts de `alerts.yml`, PromQL correto (`histogram_quantile + sum by(le)`), sem `user_id` (Livro 4 cap.5 cardinality), mounts `:ro`/`read_only`, e CI que quebra se JSON/YAML inválido.

> **Livro 4 — Prometheus Up & Running 2nd — cap.11 Grafana (p.231-260):** Dashboards são código: `provisioning/datasources/*.yml` + `provisioning/dashboards/*.yml` + `dashboards/*.json` montados `:ro`. Dashboard JSON deve ser `editable:false` em prod (versionado no git), `refresh` curto, PromQL com agregação correta (cap.6 Histograms), labels de baixa cardinalidade (cap.5). Sem provisionamento, dashboard é mutável e não-reprodutível → DR falha.

**Gate P5-03:** `95/95 → 99/99` deep hunters + `docker compose config -q` + `python -m json.tool jefrey.json` + `promtool check rules` + `pytest -q` 26 passed + `guard 6/6 PASS` + `curl /metrics | grep user_id → 0`.

---

## 2. ESTADO ATUAL — HUNT P5-02 (3 bugs + 2 warns + 1 desalinhamento)

Hunt em `docker-compose.yml` + `docker/grafana/**/*` (2026-09-02 11:56):

| # | Arquivo | Severidade | Achado | Impacto |
|---|---------|------------|--------|---------|
| **B1** | `docker-compose.yml:165-183` (grafana volumes) | **BUG** | ` - ./docker/grafana/dashboards:/var/lib/grafana` **sobrescreve** `jefrey_grafana_data:/var/lib/grafana` (mesmo mountpoint) + path errado: provisioning `dashboard.yml` espera `path: /var/lib/grafana/dashboards` mas mount entrega em `/var/lib/grafana/jefrey.json`. Resultado: provisioning falha silenciosa (`Failed to load dashboards`), dashboard só aparece se criado manualmente — viola Livro 4 cap.11 provisionamento por código. | P8 deploy: dashboard vazio após `docker volume rm`. |
| **B2** | `docker-compose.yml:165-183` (grafana volumes) | **BUG** | Mounts sem `:ro` e sem `read_only: true` na grafana (prometheus já tem `:ro` desde P5-02). Viola Axiom #4 Least Privilege + `guard_anti_patterns.sh` GREP-6B espera `:/app:ro` mas não cobre grafana; subir priv pode sobrescrever dashboards em prod. | Fail-open: container grafana pode escrever em host. |
| **B3** | `docker/grafana/dashboards/jefrey.json` (paineis + PromQL) | **BUG** | 6 painéis **desalinhados** dos 6 alerts SLO: tem `LLM Latency`, `Tokens & Cost`, `MCP Calls` (não alertados) e **falta** `ConfigInvalid`, `RateLimitDenialsHigh`, `KidLegacyHigh`, `MemoryLatencyHigh p95>300ms` (alerts 1,3,4,5). PromQL `histogram_quantile(0.50, rate(jefrey_llm_latency_seconds_bucket[5m]))` **sem `sum by(le)`** → quantile por série, não global (Livro 4 cap.6 p.135 exige `histogram_quantile(0.95, sum(rate(..._bucket[5m])) by (le))`). Mesmo erro se copiar para memória. | SLO invisível: operador não vê Memory p95 nem KidLegacy no Grafana. |
| **W1** | `docker/grafana/dashboards/jefrey.json` | **WARN** | `editable: true` + sem `overwrite` lock — dashboard mutável em prod; Livro 4 cap.11 recomenda `editable:false` quando provisionado via git (evita drift). | Drift manual não versionado. |
| **W2** | `docker/grafana/provisioning/datasources/datasource.yml` | **WARN** | OK mas sem `orgId: 1` explícito e sem `jsonData.httpMethod/exemplars`. Não quebra, mas diverge do exemplo cap.11 p.238. | Menor. |
| **W3** | `docker/grafana/dashboards/jefrey.json` | **WARN** | Templating vazio mas sem variável `datasource` — cada panel hard-coded `uid: PBFA97CFB590B2093`. Funciona, mas cap.11 recomenda template para multi-env. Mantido hard-coded nesta fase (KISS). | Não bloqueia. |

**Conclusão hunt:** B1+B2+B3 bloqueiam P5-03. W1 corrigido junto. W2/W3 aceitos.

**Métrica de sucesso:** após fix, `docker compose config` mostra `/var/lib/grafana/dashboards:ro` distinto de `/var/lib/grafana` volume, `cat /var/lib/grafana/dashboards/jefrey.json` dentro do container OK, 8 painéis SLO-alinhados, `histogram_quantile` com `sum by(le)`.

---

## 3. REFERÊNCIAS (Livro + Axiom + CIPHER)

| Ref | Trecho | Uso em P5-03 |
|-----|--------|--------------|
| **Livro 4 cap.11** p.231-245 Provisioning | `provisioning/datasources/*.yml` + `provisioning/dashboards/*.yml` (`path: /var/lib/grafana/dashboards`) + `GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH` | Fix B1: mounts separados `:ro` |
| **Livro 4 cap.11** p.245-260 Dashboards as Code | Dashboard JSON provisionado `editable:false`, `refresh 10s`, `schemaVersion 39` (Grafana 11), panels `timeseries/stat/barchart` | Fix B3: 8 painéis SLO |
| **Livro 4 cap.6** p.130-145 Histograms | `histogram_quantile(0.95, sum(rate(metric_bucket[5m])) by (le))` — **sempre** agregar por `le` antes do quantile | Fix B3 PromQL |
| **Livro 4 cap.5** p.89-102 Cardinality | Labels alta cardinalidade (`user_id`) → explosão séries; dashboard **NUNCA** template por `user_id` (ver `METRICS_CARDINALITY.md` <800 séries) | Guard: grep `user_id` em dashboard JSON → 0 |
| **Livro 4 cap.10** p.201-220 Alerting | Alerts com `for` + `severity` → dashboard deve visualizar `ALERTS{alertname=~"Jefrey.*"}` panel opcional | Painel 8 opcional ALERTS |
| **Axiom #1 Fail-Closed** | Se provisioning falha, Grafana sobe mas sem dashboard → operador sem visibilidade → deploy deve falhar no CI (`jsonlint` + `yaml safe_load`) | CI gate |
| **Axiom #4 Least Privilege** | Mounts `:ro` + `read_only: true` + `tmpfs /tmp` | Fix B2 |
| **Axiom #7 Observability** | Métricas sem `user_id` + logs com `user_id` (CIPHER-010 separação) | Dashboard sem `user_id` |
| **CIPHER-010** Audit vs Observability | `user_id` em `audit.py` (Postgres JSONL) NUNCA em `metrics.py` label | Validado `grep user_id` em `jefrey.json` → 0 |
| **CIPHER-021** Silent Except | `except: pass` proibido — provisioning errors devem logar; `guard_anti_patterns.sh` GREP-3 | CI |
| **Livro 6 cap.14** Testing | Testes determinísticos: `test_p5_metrics_cardinality.py` 3 tests + novo `test_p5_grafana_dashboards.py` 4 tests | Gate 99/99 |

---

## 4. SUB-TAREFAS (40 min) — ERRADO → CORRETO

### P5-03a) Fix `docker-compose.yml` — mounts Grafana `:ro` + paths separados (5 min)

**ERRADO (atual B1+B2):**
```yaml
  grafana:
    image: grafana/grafana:11.1.0
    volumes:
      - ./docker/grafana/provisioning:/etc/grafana/provisioning
      - ./docker/grafana/dashboards:/var/lib/grafana
      - jefrey_grafana_data:/var/lib/grafana
```

**CORRETO:**
```yaml
  grafana:
    image: grafana/grafana:11.1.0
    read_only: true
    tmpfs:
      - /tmp
    volumes:
      - ./docker/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./docker/grafana/dashboards:/var/lib/grafana/dashboards:ro
      - jefrey_grafana_data:/var/lib/grafana
    #            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ :ro + path /dashboards distinto do volume de dados
```

**Por que:** Livro 4 cap.11 p.238: provisioning datasource `path: /var/lib/grafana/dashboards` deve bater com mount. `:ro` + `read_only: true` = Axiom #4. `tmpfs /tmp` Grafana precisa escrever cache.

**Grep de aceite:** `grep -q "grafana/dashboards:/var/lib/grafana/dashboards:ro" docker-compose.yml`

---

### P5-03b) Fix `provisioning` YAMLs — datasource + dashboards provider (5 min)

**ERRADO (datasource.yml atual — funciona mas sem orgId):**
```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    uid: PBFA97CFB590B2093
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      timeInterval: "15s"
```

**CORRETO (cap.11 p.238 completo):**
```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    orgId: 1
    uid: PBFA97CFB590B2093
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      timeInterval: "15s"
      httpMethod: "POST"
      exemplarTraceIdDestinations: []
```

**ERRADO (dashboard.yml — path ok mas sem allowUiUpdates):**
```yaml
apiVersion: 1
providers:
  - name: "Jefrey"
    orgId: 1
    folder: "Jefrey"
    type: file
    disableDeletion: false
    editable: true
    updateIntervalSeconds: 30
    options:
      path: /var/lib/grafana/dashboards
```

**CORRETO:**
```yaml
apiVersion: 1
providers:
  - name: "Jefrey"
    orgId: 1
    folder: "Jefrey"
    type: file
    disableDeletion: false
    editable: true
    allowUiUpdates: true
    updateIntervalSeconds: 10
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: false
```

**Validação:** `python -c "import yaml; yaml.safe_load(open('docker/grafana/provisioning/datasources/datasource.yml')); yaml.safe_load(open('docker/grafana/provisioning/dashboards/dashboard.yml')); print('YAML OK')"`

---

### P5-03c) Rewrite `dashboards/jefrey.json` — 8 painéis SLO-alinhados + PromQL correto (20 min) — CORAÇÃO

**ERRADO (atual — 6 painéis desalinhados + PromQL sem sum by(le)):**
```json
{
  "panels": [
    {"title": "LLM Latency (P50 / P95 / P99)", "targets": [{"expr": "histogram_quantile(0.50, rate(jefrey_llm_latency_seconds_bucket[5m]))"}]},
    {"title": "Tokens & Cost", "targets": [{"expr": "sum(increase(jefrey_llm_tokens_total[1h]))"}]},
    {"title": "Service Health", "targets": [{"expr": "jefrey_service_health{component=\"api\"}"}]},
    {"title": "Tools Blocked", "targets": [{"expr": "increase(jefrey_tools_blocked_total[1h])"}]},
    {"title": "Approvals HITL", "targets": [{"expr": "increase(jefrey_approvals_created_total[1h])"}]},
    {"title": "MCP Calls", "targets": [{"expr": "rate(jefrey_mcp_calls_total[5m])"}, {"expr": "histogram_quantile(0.95, rate(jefrey_mcp_latency_seconds_bucket[5m]))"}]}
  ]
}
```
Problemas: faltam ConfigInvalid, RateLimit, KidLegacy, Memory p95; PromQL sem `sum by(le)`; `Service Health` usa métrica inexistente `jefrey_service_health` (real é `up{job="jefrey-api"}` + `jefrey_config_valid`).

**CORRETO (8 painéis — 1:1 com alerts.yml + METRICS_CARDINALITY 13 métricas):**

Painéis (grid 24 col, 3 linhas):

| # | Título | Tipo | PromQL (Livro 4 cap.6 correto) | Alerta correspondente |
|---|--------|------|--------------------------------|-----------------------|
| 1 | **Config Valid** | `stat` | `jefrey_config_valid` (0=DOWN 1=UP, mapping vermelho/verde) | `JefreyConfigInvalid` (1m critical) |
| 2 | **Service Up** | `stat` | `up{job="jefrey-api"}` + `up{job="prometheus"}` | `JefreyServiceDown` |
| 3 | **Error Rate 5m** | `timeseries` | `sum(rate(jefrey_tools_blocked_total[5m])) / clamp_min(sum(rate(jefrey_tool_exec_latency_seconds_count[5m])),1)` — threshold 0.01 vermelho | `JefreyApiHighErrorRate >1%` |
| 4 | **Rate-Limit Deny 5m** | `timeseries` | `sum(rate(jefrey_rate_limit_total{decision="deny"}[5m])) / clamp_min(sum(rate(jefrey_rate_limit_total[5m])),1)` — threshold 0.001 | `JefreyRateLimitDenialsHigh >0.1%` |
| 5 | **Memory p95 (HNSW)** | `timeseries` | `histogram_quantile(0.95, sum(rate(jefrey_memory_latency_seconds_bucket[5m])) by (le))` — threshold 0.3s | `JefreyMemoryLatencyHigh p95>300ms` |
| 6 | **Kid Legacy 10m** | `stat` + `timeseries` | `increase(jefrey_eventbus_kid_legacy_total[10m])` — threshold 10 | `JefreyKidLegacyHigh >10/10m` |
| 7 | **Tools Blocked by Reason** | `barchart` | `increase(jefrey_tools_blocked_total[1h])` `{{tool_name}} ({{reason}})` | — observabilidade HITL |
| 8 | **Approvals HITL** | `barchart` | `increase(jefrey_approvals_created_total[1h])` + `decided` | — RBAC |

**Snippet CORRETO para painel 5 (exemplo Livro 4 cap.6 p.135):**
```json
{
  "title": "Memory p95 (HNSW)",
  "type": "timeseries",
  "datasource": {"type": "prometheus", "uid": "PBFA97CFB590B2093"},
  "fieldConfig": {"defaults": {"unit": "s", "thresholds": {"steps": [{"color": "green", "value": null}, {"color": "red", "value": 0.3}]}}},
  "targets": [
    {"expr": "histogram_quantile(0.95, sum(rate(jefrey_memory_latency_seconds_bucket[5m])) by (le))", "legendFormat": "p95", "refId": "A"},
    {"expr": "histogram_quantile(0.50, sum(rate(jefrey_memory_latency_seconds_bucket[5m])) by (le))", "legendFormat": "p50", "refId": "B"}
  ]
}
```

**Regras JSON (cap.11):**
- `editable: false` (provisionado), `refresh: "10s"`, `schemaVersion: 39`, `uid: "jefrey-main"`, `tags: ["jefrey","observability"]`
- Cada panel `datasource.uid = PBFA97CFB590B2093` (ou `null` para default — escolhemos uid explícito)
- **NUNCA** `user_id` em `expr` ou `templating.list` (Livro 4 cap.5 + `METRICS_CARDINALITY.md` — grep deve dar 0)

**Grep de aceite:**
```bash
python -m json.tool docker/grafana/dashboards/jefrey.json > /dev/null && echo "JSON OK"
grep -c '"title"' docker/grafana/dashboards/jefrey.json  # -> 8
grep -c 'histogram_quantile.*sum.*by (le)' docker/grafana/dashboards/jefrey.json  # -> >=2 (p50+p95)
grep -c 'user_id' docker/grafana/dashboards/jefrey.json  # -> 0
```

---

### P5-03d) CI + pre-commit — `jsonlint` + `yaml safe_load` Grafana (5 min) (Livro 6 cap.14 + CIPHER-021)

**ERRADO (ci.yml atual P5-02 — só promtool, sem grafana):**
```yaml
  promtool-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker run --entrypoint promtool -v $PWD/docker/prometheus:/etc/prometheus prom/prometheus:v2.53.0 check rules /etc/prometheus/alerts.yml
```

**CORRETO (adicionar job grafana-lint):**
```yaml
  grafana-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Grafana JSON lint
        run: python -m json.tool docker/grafana/dashboards/jefrey.json > /dev/null && echo "jefrey.json JSON OK"
      - name: Grafana provisioning YAML lint
        run: python -c "import yaml, pathlib; yaml.safe_load(open('docker/grafana/provisioning/datasources/datasource.yml')); yaml.safe_load(open('docker/grafana/provisioning/dashboards/dashboard.yml')); print('provisioning YAML OK')"
      - name: Grafana dashboard no user_id (Livro4 cap5)
        run: "! grep -qi user_id docker/grafana/dashboards/jefrey.json && echo 'no user_id OK' || (echo 'BUG user_id in dashboard' && exit 1)"
      - name: Grafana PromQL sum by(le) check
        run: "grep -q 'histogram_quantile.*sum.*by (le)' docker/grafana/dashboards/jefrey.json && echo 'PromQL histogram OK' || (echo 'BUG PromQL missing sum by(le)' && exit 1)"
```

**pre-commit (`.pre-commit-config.yaml`):**
```yaml
  - repo: local
    hooks:
      - id: grafana-json-lint
        name: Grafana dashboard JSON lint
        entry: python -m json.tool docker/grafana/dashboards/jefrey.json
        language: system
        files: ^docker/grafana/dashboards/jefrey\.json$
      - id: grafana-yaml-lint
        name: Grafana provisioning YAML lint
        entry: python -c "import yaml; yaml.safe_load(open('docker/grafana/provisioning/datasources/datasource.yml')); yaml.safe_load(open('docker/grafana/provisioning/dashboards/dashboard.yml'))"
        language: system
        files: ^docker/grafana/provisioning/
```

---

### P5-03e) Deep gate Q + `guard` + `pytest` + `compose config` (5 min)

**Gate novo `scripts/_validate_deep.py` — seção Q (P5-03):**

```python
print("== Q. P5-03 Grafana (L4 cap11) ==")
_txt_comp = read("docker-compose.yml")
if "grafana/dashboards:/var/lib/grafana/dashboards:ro" in _txt_comp:
    oks.append("compose grafana dashboards :ro + path /dashboards OK (P5-03 B1)")
else:
    bugs.append("compose grafana dashboards sem :ro ou path errado (P5-03 B1 cap11)")
if "grafana/provisioning:/etc/grafana/provisioning:ro" in _txt_comp:
    oks.append("compose grafana provisioning :ro OK (P5-03 B2)")
else:
    bugs.append("compose grafana provisioning sem :ro (P5-03 B2)")
if "read_only: true" in _txt_comp and _txt_comp.count("read_only: true") >= 3:  # jefrey-api + mcp-server + grafana
    oks.append("compose grafana read_only OK (P5-03 B2)")
else:
    warns.append("compose grafana read_only maybe missing")
# provisioning YAMLs
for _p in ["docker/grafana/provisioning/datasources/datasource.yml","docker/grafana/provisioning/dashboards/dashboard.yml"]:
    try:
        import yaml as _y; _y.safe_load(open(_p))
        oks.append(f"{_p} YAML safe_load OK")
    except Exception as _e:
        bugs.append(f"{_p} YAML invalid: {_e}")
# dashboard JSON
try:
    import json as _j; _d=_j.load(open("docker/grafana/dashboards/jefrey.json"))
    oks.append("jefrey.json JSON valid OK")
    _panels=_d.get("panels",[])
    if len(_panels) >= 8:
        oks.append(f"jefrey.json 8 panels OK ({len(_panels)})")
    else:
        bugs.append(f"jefrey.json panels {len(_panels)} <8 (P5-03 B3)")
    _raw=open("docker/grafana/dashboards/jefrey.json").read()
    if "user_id" in _raw.lower():
        bugs.append("jefrey.json contem user_id -> cardinality BUG (L4 cap5)")
    else:
        oks.append("jefrey.json no user_id OK (L4 cap5)")
    if "histogram_quantile" in _raw and "sum(" in _raw and "by (le)" in _raw:
        oks.append("jefrey.json PromQL histogram sum by(le) OK (L4 cap6)")
    else:
        bugs.append("jefrey.json PromQL sem sum by(le) (L4 cap6 B3)")
    if _d.get("editable") is False:
        oks.append("jefrey.json editable false OK (cap11)")
    else:
        warns.append("jefrey.json editable true -> drift risk (cap11)")
    _exprs=" ".join([t.get("expr","") for p in _panels for t in p.get("targets",[])])
    for _need in ["jefrey_config_valid","jefrey_memory_latency_seconds_bucket","jefrey_rate_limit_total","jefrey_eventbus_kid_legacy_total"]:
        if _need in _exprs:
            oks.append(f"jefrey.json expr {_need} OK")
        else:
            bugs.append(f"jefrey.json falta expr {_need} (SLO)")
except Exception as _e:
    bugs.append(f"jefrey.json erro: {_e}")
```

**Meta:** `95/95 (P5-02) → 99/99` (4 novos gates) = 100%.

**Pytest novo `tests/test_p5_grafana_dashboards.py` (4 tests — Livro 6 cap.14):**
- `test_grafana_json_valid_and_panels_ge_8`
- `test_grafana_no_user_id_label` (cap.5)
- `test_grafana_promql_histogram_sum_by_le` (cap.6)
- `test_grafana_compose_mounts_ro` (cap.11)

**Guard:** `bash scripts/guard_anti_patterns.sh` → `6/6 PASS` (já cobre `:ro` mas adicionar check `grafana/dashboards`).

---

## 5. ORDEM DE EXECUÇÃO (40 min wall-clock)

```
[00-05] P5-03a compose mounts :ro + read_only + tmpfs
[05-10] P5-03b provisioning YAMLs fix (orgId, httpMethod, allowUiUpdates, updateInterval 10s)
[10-30] P5-03c jefrey.json rewrite 8 paineis + PromQL sum by(le) + editable false
[30-35] P5-03d CI grafana-lint + pre-commit hooks
[35-40] P5-03e deep gate Q 99/99 + pytest 26 + guard + promtool + compose config -q
```

**Antes de cada commit (diretriz PLANO_FASE_P5_OBSERVABILITY.md):**
```bash
bash scripts/guard_anti_patterns.sh          # 6/6
python -m pytest -q                          # 26 passed
python -m py_compile $(git ls-files "*.py")  # 0
python -m compileall -q src
docker compose config -q && echo "compose OK"
python -m json.tool docker/grafana/dashboards/jefrey.json > /dev/null && echo "json OK"
python -c "import yaml; yaml.safe_load(open('docker/grafana/provisioning/datasources/datasource.yml')); yaml.safe_load(open('docker/grafana/provisioning/dashboards/dashboard.yml'))" && echo "yaml OK"
docker run --rm --entrypoint promtool -v $PWD/docker/prometheus:/etc/prometheus prom/prometheus:v2.53.0 check rules /etc/prometheus/alerts.yml
```

---

## 6. CRITÉRIOS DE ACEITE (Definition of Done)

- [ ] `docker-compose.yml` grafana: `read_only: true` + `tmpfs: /tmp` + `:/etc/grafana/provisioning:ro` + `:/var/lib/grafana/dashboards:ro` (distinto de `jefrey_grafana_data:/var/lib/grafana`)
- [ ] `datasource.yml` + `dashboard.yml` `yaml.safe_load` OK + `orgId:1` + `updateIntervalSeconds:10`
- [ ] `jefrey.json` JSON válido, `editable:false`, `schemaVersion:39`, `refresh 10s`, **8 panels** (Config, Up, ErrorRate, RateLimit, Memory p95, KidLegacy, Tools Blocked, Approvals), cada com `datasource.uid=PBFA97CFB590B2093`
- [ ] PromQL histograms com `histogram_quantile(..., sum(rate(..._bucket[5m])) by (le))` (grep `sum.*by (le)` ≥2)
- [ ] `grep -qi user_id docker/grafana/dashboards/jefrey.json` → 0 (Livro 4 cap.5)
- [ ] `ci.yml` job `grafana-lint` + `.pre-commit-config.yaml` hooks `grafana-json-lint`/`grafana-yaml-lint`
- [ ] `scripts/_validate_deep.py` seção Q adicionada → `99/99 100%` (vs 95/95 P5-02)
- [ ] `tests/test_p5_grafana_dashboards.py` 4 tests → `pytest -q` 26 passed (22 P5-01/02 + 4 P5-03)
- [ ] `bash scripts/guard_anti_patterns.sh` 6/6 PASS + `docker compose config -q` OK + `promtool check rules` 6 rules OK + `json.tool` OK
- [ ] Commit `P5-03 Grafana 8 panels SLO + provisioning :ro (Livro4 cap11, 99/99)` com `guard+pytest+compileall+compose+jsonlint` verdes

---

## 7. RISCOS + ROLLBACK

| Risco | Mitigação |
|-------|-----------|
| Grafana não sobe após `read_only: true` (precisa escrever em `/var/lib/grafana`) | `jefrey_grafana_data:/var/lib/grafana` permanece RW para dados; apenas `provisioning` e `dashboards` são `:ro`. `tmpfs /tmp` para cache. Teste `docker compose up grafana --no-deps` local. |
| Dashboard JSON inválido (trailing comma) trava provisioning silencioso | CI `json.tool` + `deep gate` quebra antes do merge. Rollback: `git revert <commit>` — dashboard volta aos 6 painéis. |
| `updateIntervalSeconds: 10` muito agressivo | Ajuste para 30s se logs mostrarem reload frequente; não afeta SLO. |
| Painel PromQL sem dados (ex.: `jefrey_llm_*` removido) | Painel mostra `No data` mas não quebra. P5-03 painéis usam apenas métricas garantidas por `METRICS_CARDINALITY.md` (config, up, rate_limit, kid_legacy, memory) — sempre presentes. LLM panels removidos. |

---

## 8. REFERÊNCIAS CRUZADAS

- **PLANO_FASE_P5_OBSERVABILITY.md** 3 h (P5-01 cardinality 45m DONE, P5-02 promtool 20m DONE, P5-03 grafana 40m ESTE, P5-04 drill 45m, P5-05 fallback 25m, P5-06 CI 20m)
- **PLANO_FASE_P5-02_PROMTOOL.md** 305 linhas (rule_files, alerts 6/6, compose :ro, ci promtool, deep gate Q) — base para P5-03d
- **PLANO_FASE_P5-01_METRICS_CARDINALITY.md** — inventário 13 métricas, `<800` séries, `grep user_id → 0`
- **SLO_RUNBOOK.md v1.1 FINAL** + **THREAT_MODEL.md v1.1 FINAL** — SLOs que geram os 8 painéis
- **ADR-001-kid-rotation.md** — métrica global `kid_legacy_total` sem label

---

## 9. ANEXO — COMANDO DE HUNT REPRODUZÍVEL (pessimista)

```bash
# Hunt P5-03 bugs antes do fix (deve mostrar B1+B2+B3)
grep -n "grafana" docker-compose.yml
cat docker-compose.yml | grep -A2 "grafana:"
python -m json.tool docker/grafana/dashboards/jefrey.json > /dev/null && echo "JSON OK" || echo "JSON FAIL"
grep -c '"title"' docker/grafana/dashboards/jefrey.json
grep -c 'histogram_quantile.*sum.*by (le)' docker/grafana/dashboards/jefrey.json || echo "0 -> B3"
grep -qi user_id docker/grafana/dashboards/jefrey.json && echo "BUG user_id" || echo "no user_id OK"
python -c "import yaml; yaml.safe_load(open('docker/grafana/provisioning/datasources/datasource.yml')); print('datasource YAML OK')"
python -c "import yaml; yaml.safe_load(open('docker/grafana/provisioning/dashboards/dashboard.yml')); print('dashboard YAML OK')"
docker compose config -q && echo "compose OK" || echo "compose FAIL"
```

**Próximo passo:** executar P5-03a→e em sequência, rodar `guard+pytest+compileall+jsonlint+yaml+compose+promtool` antes de `git commit -m "P5-03 Grafana 8 panels SLO + provisioning :ro (Livro4 cap11, 99/99)"`.

