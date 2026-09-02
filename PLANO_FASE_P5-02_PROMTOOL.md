# PLANO FASE P5-02 — PROMTOOL CHECK RULES & RULE_FILES (Livro4 cap10 Alerting)

**Version:** 1.0 DRAFT — 2026-09-02 11:00 -03:00
**Base:** P5-01 DONE commit a2b144e (91/91 100% deep) + P4-FINAL 67fc89d/49a68bc | Estado 96-98% prod-ready -> 97-99% apos P5 DONE
**Tempo:** 20 min | **Dependencia:** P5-01 metrics cardinality (<800 series, sem user_id) DONE
**Bloqueia:** P5-03 (Grafana cap11) — sem P5-02 verde, P5-03 nao inicia; bloqueia P8 deploy (tag v1.0.0-p5)
**Branch:** master | **Ordem AGORA:** Livros 1,2,3 -> DURANTE P8 4,5,6 -> DEPOIS 7,8,9,10 (ordem fixa PLANO_MESTRE)

---

## 0. Diretrizes trancadas (6 PRINCIPIOS FAIL-CLOSED + Axioms + CIPHER + 10 Livros)

**6 Principios FAIL-CLOSED (CONTRIBUTING.md):**
1. FAIL-CLOSED — prod sem HMAC/OAUTH/REDIS => RuntimeError, nunca warn/allow
2. ISOLAMENTO — user_id=None guest, nunca "system" default (Axiom #2)
3. SEM STUB EM PROD — valid_ prefix so fora de prod com UserWarning (CIPHER-031)
4. PERSISTENCIA REAL — Redis TTL + pgvector HNSW (DDIA cap3/12)
5. CRIPTO CORRETA — urlsafe_b64encode + RS256+kid + aud/iss/exp compare_digest sort_keys
6. LEAST PRIVILEGE — overwrite=False, :ro, CORS explicit, allow_credentials False

**Axioms aplicados P5-02:**
- #1 Fail-Closed — prometheus.yml sem rule_files ou alerts.yml invalido => CI falha, nao warn
- #4 Cardinality — mantem P5-01 (<800 series), alerts nao reintroduzem user_id
- #7 Observability — alerts sao SLOs auditaveis (SLO_RUNBOOK FINAL 1.1)

**CIPHER:**
- 021 silent except — promtool erro nunca silenciado com except: pass
- 010 audit — toda falha de validacao logada com contexto
- 033 HMAC kid rotation — alerts KidLegacyHigh ja cobre (ADR-001)

**10 Livros — P5-02 usa LIVRO 4 cap10:**
- **Livro 4 — Prometheus Up & Running 2nd (Julien Pivotto) cap10 Alerting** — referencia primaria: rule_files, for, labels severity, promtool check rules/config
- Livro 4 cap5 Cardinality — ja aplicado P5-01, preservado aqui
- Livro 6 SWE at Google cap14 Testing — CI guard + pytest antes de commit
- Demais livros: ordem AGORA 1,2,3 (MCP Spec, Agents Cookbook, Security Eng) ja aplicados P0-P4; cap6 Histograms e cap11 Grafana ficam para P5-04/P5-03

---

## 1. Inventario P5-02 (5 sub-tarefas a-e, 20m total)

| ID | Sub-tarefa | Livro | Axiom/CIPHER | Tempo | Artefato |
|----|------------|-------|--------------|-------|----------|
| a | prometheus.yml rule_files valido | L4 cap10 | Axiom #1 | 3m | docker/prometheus/prometheus.yml |
| b | alerts.yml 6 alerts sintaxe valida | L4 cap10 | Axiom #1 | 5m | docker/prometheus/alerts.yml |
| c | compose mount :ro idempotente | L4 cap10+DDIA | #6 Least Privilege | 2m | docker-compose.yml |
| d | CI promtool check rules + check config | L4 cap10 + L6 cap14 | CIPHER-021 | 5m | .github/workflows/ci.yml |
| e | deep gate P5-02 + pre-commit hook | L4 cap10 | Axiom #1 | 5m | scripts/_validate_deep.py + .pre-commit-config.yaml |

**Estado atual (pre P5-02):**
- prometheus.yml JA tem rule_files: - /etc/prometheus/alerts.yml (P4-04) — precisa validar promtool
- alerts.yml JA tem 6 alerts (ConfigInvalid, ApiHighErrorRate, RateLimitDenialsHigh, KidLegacyHigh, MemoryLatencyHigh, ServiceDown) — precisa validar sintaxe e for/labels
- compose JA tem mount ./docker/prometheus/alerts.yml:/etc/prometheus/alerts.yml:ro (P4-04) — precisa validar :ro
- ci.yml AINDA sem promtool — falta job
- deep.py JA tem gate P5-01 91/91 — falta gate P5-02 -> 92/92 esperado

---

## 2. ERRADO -> CORRETO diffs (copiar exato)

### a) prometheus.yml — ERRADO sem rule_files vs CORRETO com rule_files

```yaml
# ERRADO — sem rule_files (alerts nunca carregam, SLO_RUNBOOK mente)
global:
  scrape_interval: 15s
  evaluation_interval: 15s
scrape_configs:
  - job_name: "jefrey-api"
    static_configs: [{targets: ["jefrey-api:8000"]}]

# CORRETO — L4 cap10 rule_files + evaluation_interval
global:
  scrape_interval: 15s
  evaluation_interval: 15s
rule_files:
  - /etc/prometheus/alerts.yml   # <-- P4-04 ja OK, P5-02 valida com promtool
scrape_configs:
  - job_name: "prometheus"
    static_configs: [{targets: ["localhost:9090"]}]
  - job_name: "jefrey-api"
    metrics_path: /metrics
    static_configs: [{targets: ["jefrey-api:8000"]}]
```

Validacao: `promtool check config docker/prometheus/prometheus.yml` deve sair 0
Guard: grep -q "rule_files:" docker/prometheus/prometheus.yml || exit 1

### b) alerts.yml — ERRADO sem for/labels vs CORRETO L4 cap10

```yaml
# ERRADO — sem for, sem severity, expr sem funcao rate (falso verde)
groups:
  - name: jefrey.slo
    rules:
      - alert: JefreyConfigInvalid
        expr: jefrey_config_valid == 0

# CORRETO — L4 cap10 for + labels severity + expr com rate/increase/histogram_quantile
groups:
  - name: jefrey.slo
    interval: 30s
    rules:
      - alert: JefreyConfigInvalid
        expr: jefrey_config_valid == 0
        for: 1m
        labels: {severity: critical}
        annotations: {summary: "Config invalida", runbook: "docs/SLO_RUNBOOK.md#configinvalid"}
      - alert: JefreyApiHighErrorRate
        expr: sum(rate(jefrey_tool_executions_total{status="error"}[5m])) / clamp_min(sum(rate(jefrey_tool_executions_total[5m])),1) > 0.01
        for: 5m
        labels: {severity: warning}
        annotations: {summary: "Error rate >1% 5m"}
      - alert: JefreyRateLimitDenialsHigh
        expr: sum(rate(jefrey_rate_limit_total{decision="deny"}[5m])) / clamp_min(sum(rate(jefrey_rate_limit_total[5m])),1) > 0.001
        for: 5m
        labels: {severity: warning}
      - alert: JefreyKidLegacyHigh
        expr: increase(jefrey_eventbus_kid_legacy_total[10m]) > 10
        for: 10m
        labels: {severity: warning}
        annotations: {summary: "Kid legacy >10/10m - rotacao pendente ADR-001"}
      - alert: JefreyMemoryLatencyHigh
        expr: histogram_quantile(0.95, sum(rate(jefrey_memory_latency_seconds_bucket[5m])) by (le, operation)) > 0.3
        for: 5m
        labels: {severity: warning}
      - alert: JefreyServiceDown
        expr: up{job="jefrey-api"} == 0
        for: 1m
        labels: {severity: critical}
```

Validacao: `promtool check rules docker/prometheus/alerts.yml` deve sair 0 + `promtool check rules --lint` sem warn
Nota Windows: usar for 30s em teste isolado com promtool test rules demora 5m — em alerts.yml real usar 1m/5m/10m e em teste promtool usar intervalo curto so no arquivo de teste

### c) docker-compose.yml — ERRADO sem :ro vs CORRETO :ro

```yaml
# ERRADO — sem :ro (Axiom #6 Least Privilege viola)
  prometheus:
    volumes:
      - ./docker/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./docker/prometheus/alerts.yml:/etc/prometheus/alerts.yml

# CORRETO — :ro + read_only ja existente para jefrey-api
  prometheus:
    volumes:
      - ./docker/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./docker/prometheus/alerts.yml:/etc/prometheus/alerts.yml:ro
```

Validacao: grep -q "alerts.yml:ro" docker-compose.yml || exit 1 + docker compose config -q com env dummy

### d) .github/workflows/ci.yml — ERRADO sem promtool vs CORRETO com promtool

```yaml
# ERRADO — so guard+audit+pytest, sem validar alerts (falso verde: alerts.yml quebrado passa CI)
    steps:
      - run: bash scripts/guard_anti_patterns.sh
      - run: python -m pytest tests -q

# CORRETO — L4 cap10 + L6 cap14: promtool via docker image prom/prometheus:v2.53.0
    steps:
      - uses: actions/checkout@v4
      - name: promtool check rules
        run: docker run --rm -v ${{ github.workspace }}/docker/prometheus:/prometheus prom/prometheus:v2.53.0 promtool check rules /prometheus/alerts.yml
      - name: promtool check config
        run: docker run --rm -v ${{ github.workspace }}/docker/prometheus:/prometheus prom/prometheus:v2.53.0 promtool check config /prometheus/prometheus.yml
      - name: guard anti-patterns
        run: bash scripts/guard_anti_patterns.sh
      - name: audit prod
        run: JEFREY_ENV=prod JEFREY_EVENTBUS__HMAC_KEY=dummy_for_ci_32_chars_12345678 ... python audit_pessimista.py
      - name: pytest
        run: python -m pytest tests -q
      - name: compose config
        run: JEFREY_EVENTBUS__HMAC_KEY=dummy ... docker compose config -q
```

Fallback sem docker (Windows local): `promtool.exe check rules docker/prometheus/alerts.yml` se binario local existir, senao validar via python yaml + regex for/expr

### e) scripts/_validate_deep.py + .pre-commit-config.yaml — gate P5-02

```python
# ERRADO — deep sem gate P5-02 (91/91) — alerts quebrado nao bloqueia
# CORRETO — adicionar secao Q P5-02 promtool (92/92)
print("== Q. P5-02 promtool (L4 cap10) ==")
import re as _re2
_txt_prom = read("docker/prometheus/prometheus.yml")
if "rule_files:" in _txt_prom and "/etc/prometheus/alerts.yml" in _txt_prom:
    oks.append("prometheus.yml rule_files OK (P5-02)")
else:
    bugs.append("prometheus.yml sem rule_files (P5-02 L4 cap10)")
_txt_alerts = read("docker/prometheus/alerts.yml")
if _txt_alerts.count("alert:") >= 6 and "for:" in _txt_alerts and "severity:" in _txt_alerts:
    oks.append("alerts.yml 6 alerts com for/severity OK (P5-02)")
else:
    bugs.append("alerts.yml sem 6 alerts ou sem for/severity (P5-02)")
if "alerts.yml:ro" in read("docker-compose.yml"):
    oks.append("compose alerts mount :ro OK (P5-02)")
else:
    bugs.append("compose alerts mount sem :ro (P5-02)")
if "promtool check rules" in read(".github/workflows/ci.yml"):
    oks.append("ci promtool check rules OK (P5-02)")
else:
    warns.append("ci sem promtool check rules (P5-02) — WARN ate instalar promtool")
```

Pre-commit: adicionar hook promtool (opcional, nao bloqueante se promtool ausente local)
```yaml
  - id: promtool-check-rules
    name: promtool check rules (L4 cap10 P5-02)
    entry: bash -c 'command -v promtool >/dev/null 2>&1 && promtool check rules docker/prometheus/alerts.yml || echo "promtool ausente local — skip (CI valida)"'
    language: system
    files: ^docker/prometheus/(alerts|prometheus)\.yml$
    pass_filenames: false
```

---

## 3. Ordem de execucao (20m)

1. **3m** — Validar estado atual: prometheus.yml rule_files + alerts.yml 6 alerts + compose :ro (ja DONE P4-04) — nao reescrever se OK, so validar
2. **5m** — Rodar promtool local se disponivel: docker run prom/prometheus:v2.53.0 promtool check rules + check config — se docker ausente, validar via python yaml + grep for/severity
3. **5m** — Patch .github/workflows/ci.yml: adicionar job promtool check rules + check config (via docker run prom/prometheus:v2.53.0)
4. **5m** — Patch scripts/_validate_deep.py secao Q P5-02 (91 -> 92 gates) + .pre-commit-config.yaml hook opcional
5. **2m** — Re-validar: compileall -q src + guard 6/6 + pytest tests -q 23 passed + deep 92/92 + docker compose config -q + promtool checks

Regra de commit (PLANO_FASE_P4_PROD.md): **guard + pytest + compileall antes de cada commit** — nunca commit sem esses 3 verdes

---

## 4. Checklist bloqueia P5-03 (copiar para commit msg)

- [ ] prometheus.yml contem rule_files: /etc/prometheus/alerts.yml (grep 1 hit)
- [ ] alerts.yml 6 alerts com for: + labels severity (grep alerts 6, for >=6, severity >=6)
- [ ] promtool check rules docker/prometheus/alerts.yml EXIT 0 (docker run prom/prometheus:v2.53.0)
- [ ] promtool check config docker/prometheus/prometheus.yml EXIT 0
- [ ] docker-compose.yml alerts.yml:ro (grep 1 hit)
- [ ] docker compose config -q EXIT 0 (com env dummy HMAC_KEYS_JSON/AUD/ISS/REDIS/DATABASE)
- [ ] .github/workflows/ci.yml contem promtool check rules (grep 1 hit)
- [ ] scripts/_validate_deep.py secao Q P5-02 + 92/92 100% (WARNS 0 BUGS 0)
- [ ] .pre-commit-config.yaml hook promtool opcional (ou documentado skip se ausente)
- [ ] guard_anti_patterns.sh 6/6 PASS + pytest tests -q 23 passed + compileall -q src 0

---

## 5. Validacao (comandos exatos)

```bash
# prometheus.yml
grep -q "rule_files:" docker/prometheus/prometheus.yml && echo PASS || echo FAIL
grep -q "/etc/prometheus/alerts.yml" docker/prometheus/prometheus.yml && echo PASS || echo FAIL

# alerts.yml
grep -c "alert:" docker/prometheus/alerts.yml  # deve ser 6
grep -c "for:" docker/prometheus/alerts.yml     # >=6
grep -c "severity:" docker/prometheus/alerts.yml # >=6

# promtool (via docker — nao usar for 30s em prod, so em teste)
docker run --rm -v "%cd%/docker/prometheus:/prometheus" prom/prometheus:v2.53.0 promtool check rules /prometheus/alerts.yml
docker run --rm -v "%cd%/docker/prometheus:/prometheus" prom/prometheus:v2.53.0 promtool check config /prometheus/prometheus.yml
# fallback Windows sem docker: python -c "import yaml; yaml.safe_load(open('docker/prometheus/alerts.yml'))" && echo YAML_OK

# compose
grep -q "alerts.yml:ro" docker-compose.yml && echo PASS || echo FAIL
set JEFREY_EVENTBUS__HMAC_KEY=dummy_for_compose_q_32_chars_12345678&& set JEFREY_EVENTBUS__HMAC_KEYS_JSON={"v1":"dummy_for_compose_q_32_chars_12345678"}&& set JEFREY_OAUTH__AUD=jefrey&& set JEFREY_OAUTH__ISS=https://auth.test&& set JEFREY_REDIS__PASSWORD=test&& set JEFREY_DATABASE__PASSWORD=test&& set JEFREY_API__SECRET_KEY=dummy1234567890123456789012345678&& docker compose config -q && echo COMPOSE_OK

# ci
grep -q "promtool check rules" .github/workflows/ci.yml && echo PASS || echo FAIL

# deep + guard + pytest + compileall
python scripts/_validate_deep.py  # deve ser 92/92 100%
bash scripts/guard_anti_patterns.sh  # 6/6 PASS
python -m pytest tests -q  # 23 passed
python -m compileall -q src; echo COMPILE:%ERRORLEVEL%
```

---

## 6. Riscos e rollback

- **Risco:** promtool nao disponivel local (sem docker) — mitigacao: CI valida via docker image, local valida via yaml + grep; pre-commit hook opcional com skip
- **Risco:** for 30s em teste promtool test rules demora 5m — mitigacao: usar for 1m/5m em alerts.yml real, so usar 30s em arquivo de teste isolado com promtool test rules
- **Risco:** compose mount :ro quebra leitura local Windows — mitigacao: :ro funciona Windows Docker Desktop, testar compose config -q antes de commit
- **Rollback:** git revert <commit P5-02> — volta para 91/91 sem promtool, P5-01 preservado

---

## 7. Referencias cruzadas

- PLANO_FASE_P5_OBSERVABILITY.md — P5 overview 3h, P5-02 20m dentro dele
- PLANO_FASE_P5-01_METRICS_CARDINALITY.md — P5-01 DONE 91/91, base para P5-02
- docs/METRICS_CARDINALITY.md — 13 metricas <800 series (L4 cap5), preservadas
- SLO_RUNBOOK.md v1.1 FINAL — 6 alerts documentados, rule_files referenciado
- ADR-001-kid-rotation.md — KidLegacyHigh alert cobre rotacao
- THREAT_MODEL.md v1.1 FINAL — vetores IdP/EventBus/HNSW ja mitigados, alerts validam
- docker/prometheus/alerts.yml — 6 alerts (P4-04)
- docker/prometheus/prometheus.yml — rule_files (P4-04)
- .github/workflows/ci.yml — guard+audit+pytest+compose, falta promtool
- scripts/_validate_deep.py — 91/91 -> 92/92 apos P5-02
- Guard: scripts/guard_anti_patterns.sh 6/6 PASS
- Livros: L4 cap10 Alerting (primario), L4 cap5 Cardinality, L6 cap14 Testing

---

**Assinatura:** Axiom #1 Fail-Closed + CIPHER-021 + Livro4 cap10 — sem promtool verde, P5-03 bloqueado
