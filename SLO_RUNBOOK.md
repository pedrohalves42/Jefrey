

---

## Apêndice P5-04 — Alerts Firing Drill 6/6 (2026-09-02, Livro4 cap10, Axiom #1/#6)

**Commit:** f9023f2 base + P5-04 feat | **promtool:** prom/prometheus:v2.53.0 | **Gates:** 114/114 100% (P5-04a-e)

### Como reproduzir (dev)

```bash
# 1. Validar sintaxe + firing sem subir stack (unit test, Livro4 p.228)
docker run --rm --entrypoint promtool -v %cd%/docker/prometheus:/etc/prometheus prom/prometheus:v2.53.0 check rules /etc/prometheus/alerts.yml
docker run --rm --entrypoint promtool -v %cd%/docker/prometheus:/etc/prometheus prom/prometheus:v2.53.0 test rules /etc/prometheus/tests/alerts_test.yml
# esperado: SUCCESS: 6 rules found + 6/6 PASS (alert_rule_test com eval_time)

# 2. Drill sintético isolado (sem rede, fail-closed prod)
python scripts/drill_alerts.py --help
python scripts/drill_alerts.py --alert KidLegacyHigh --count 15   # inc 15 global sem user_id
python scripts/drill_alerts.py --alert RateLimitDenialsHigh --count 20
python scripts/drill_alerts.py --alert MemoryLatencyHigh --count 50
python scripts/drill_alerts.py --alert ConfigInvalid --duration 0  # sem sleep em CI
python -c "from jefrey.core.metrics import CONFIG_VALID; print(CONFIG_VALID._value.get())"

# 3. Grafana durante firing (requere compose up)
# http://localhost:3000/d/jefrey-main — 8 panels SLO, 6 mapeiam 6 alerts, thresholds = expr alerts
# Validar: python -c "import json; j=json.load(open('docker/grafana/dashboards/jefrey.json')); print([p['title'] for p in j['panels']])"

# 4. Gates bloqueio P5-05
python -m compileall -q src && python -m json.tool docker/grafana/dashboards/jefrey.json > /dev/null
python -c "import yaml; [yaml.safe_load(open(f,encoding='utf-8')) for f in ['docker-compose.yml','docker/prometheus/prometheus.yml','docker/prometheus/alerts.yml','docker/grafana/provisioning/datasources/datasource.yml','docker/grafana/provisioning/dashboards/dashboard.yml','docker/prometheus/tests/alerts_test.yml']]; print('yaml 6/6 OK')"
bash scripts/guard_anti_patterns.sh && bash scripts/guard_grafana.sh
python -m pytest tests -q  # 31 tests (27+4 P5-04)
python scripts/_validate_deep.py  # 114/114 100%
```

### Resultado drill 2026-09-02

| # | Alert | for | severity | promtool | drill | panel |
|---|-------|-----|----------|----------|-------|-------|
| 1 | JefreyConfigInvalid | 1m | critical | PASS 4m | CONFIG_VALID 0/1 | 1 Config Valid |
| 2 | JefreyApiHighErrorRate | 5m | warning | PASS 8m | TOOLS_BLOCKED inc | 4 Error Rate |
| 3 | JefreyRateLimitDenialsHigh | 5m | warning | PASS 8m | RATE_LIMIT deny | 5 RateLimit |
| 4 | JefreyKidLegacyHigh | 5m | warning | PASS 14m | KID_LEGACY inc 15 | 3 Kid Legacy |
| 5 | JefreyMemoryLatencyHigh | 5m | warning | PASS 8m | MEMORY_LATENCY 0.9s | 6 Memory p95 |
| 6 | JefreyServiceDown | 1m | critical | PASS 4m | promtool only | 2 Service Up |

**Referências:** Livro4 cap10 p.195-230 (rule_files, for, severity, promtool test), cap6 p.132 (sum by(le) antes quantile), cap5 (1 série/alert), CIPHER-021/026/033, Axiom #1 fail-closed.

### Thresholds operacionais (sync alerts.yml == grafana)

- ConfigInvalid 0, ErrorRate 0.01, RateLimit 0.001, KidLegacy 10/10m, Memory p95 0.3s, Up 0

Artifact: `reports/p5-04-drill.log` gerado em CI e local após `python scripts/drill_alerts.py --alert all --duration 0`.
