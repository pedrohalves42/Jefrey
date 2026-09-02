# PLANO FASE P5 — OBSERVABILITY (Prometheus + Grafana + Alerts Firing)
Version: 1.0 — DRAFT 2026-09-02 — Proxima fase apos P4-FINAL (67fc89d)
Base: PLANO_MESTRE_44_ISSUES.md v1.1, PLANO_FASE_P4_PROD.md 1.1, SLO_RUNBOOK 1.1 FINAL, THREAT_MODEL 1.1 FINAL, ADR-001 kid rotation
Estado entrada: P4 100% — compileall 0 + guard 6/6 PASS + pytest 20 passed + _validate_deep 90/90 100% + compose config -q OK + audit prod 0 CRITICO + git limpo. 95-98% prod-ready pessimista (codigo). P4-04/05/06 DONE (alerts 6 + rule_files + ci + HNSW m16/ef64).
Objetivo P5: Provar observabilidade REAL sem cardinalidade infinita, com alerts firing e dashboard p95 <300ms. Bloqueia P8 deploy se falhar. Duracao 3h.

---

## 1. VEREDITO PESSIMISTA -> OTIMISTA

| Visao | % prod-ready | Gate |
|-------|--------------|------|
| Pessimista (audit_pessimista) | 95-98% apos P4-FINAL | Codigo 100% gates, mas SLOs nunca dispararam, Grafana sem screenshot, /metrics nao provado em staging, log fallback nao drillado |
| Otimista (apos P5 DONE) | 97-99% | + /metrics sem user_id + promtool 0 errors + 6 alerts firing drill + Grafana p95 <300ms + CI metrics job verde |
| P8 liberado so apos | P5 + P6 (DDIA pool/CONCURRENTLY/Streams 2-processos) | Livros 4,5,6 DURANTE P8; 7,8,9,10 DEPOIS (perf) |

P4 entregou definicao de SLOs; P5 entrega prova. Sem P5, P8 e deploy cego (quebra Axiom #6 PERSISTENCIA REAL + Livro 4 cap5).

---

## 2. 6 PRINCIPIOS FAIL-CLOSED TRANCADOS (revalidados em cada P5-xx)

1. FAIL-CLOSED — sem fallback allow; prod sem secret = RuntimeError (C1a)
2. ISOLAMENTO — user_id=None guest least-privilege; metrica NUNCA usa user_id como label (cardinalidade infinita)
3. SEM STUB EM PROD — valid_ stub so quando _is_prod()==False + UserWarning; kid legacy so via DeprecationWarning + metric EVENTBUS_KID_LEGACY_TOTAL
4. PERSISTENCIA REAL — Redis Streams XADD maxlen 10000 + DLQ jefrey:dlq:{user_id} + audit dual-write Postgres->fallback file com redact_pii
5. CRIPTO CORRETA — urlsafe_b64encode sem padding + RS256 + kid + aud/iss/exp/kid + compare_digest + sort_keys
6. LEAST PRIVILEGE — overwrite=False, :ro, read_only, allow_credentials False + CORS Origens explicitas, :?required para PASSWORD/SECRET

Checklist antes de cada commit P5 (igual P4):

    bash scripts/guard_anti_patterns.sh  # 6/6 PASS
    JEFREY_ENV=prod ... python audit_pessimista.py | findstr CRITICO  # 0
    python -m compileall -q src
    python -m pytest tests -q  # 20 passed
    docker compose config -q  # com env dummy
    curl -s http://localhost:8000/metrics | grep -v user_id  # sem user_id
    promtool check rules docker/prometheus/alerts.yml  # 0 errors

---

## 3. ORDEM DOS 10 LIVROS — REFERENCES_MAPPING.md

| Fase | Livros | Capitulos P5 | Uso |
|------|--------|--------------|-----|
| AGORA 1,2,3 DONE | 1 MCP Spec 2026-07-28, 2 OpenAI Agents Cookbook, 3 Security Eng Ross Anderson 3rd | P4 ja aplicou | Base fail-closed + JWKS + Skill Risk |
| DURANTE P8 4,5,6 — P5 usa 4 | 4 Prometheus Up & Running 2nd (Julien Pivotto) | cap 5 Cardinality, cap 6 Histograms, cap 10 Alerting, cap 11 Grafana | P5-01 cap5 (sem user_id), P5-02 cap10 (rule_files), P5-03 cap11 (dashboard), P5-04 cap6 (p95) |
| DURANTE P8 5,6 — P6 usa | 5 DDIA Kleppmann, 6 SWE at Google | cap 3 Persistence, cap 12 Tuning, cap 8 Style, cap 14 Testing | P5-05 audit fallback (DDIA cap3), P5-06 CI (SWE cap14) |
| DEPOIS 7,8,9,10 | 7 Fluent Python 19-21, 8 High Perf Python, 9 Building LLM Apps OReilly 2024, 10 Pragmatic Programmer 20th | NAO USAR em P5 | Perf so apos P5/P6 estaveis (Axiom #1) |

Regra axiomatica: Livro 4 cap5 diz "labels de ALTA cardinalidade (user_id, email, request_id) matam Prometheus". P5-01 prova que nenhum metric usa user_id. Livro 4 cap10 exige rule_files + for + labels severity/slo.

---

## 4. INVENTARIO P5 — 6 ITENS (3h)

| ID | Titulo | Severidade | Axiom | CIPHER | Livro | Tempo | Bloqueia |
|----|--------|------------|-------|--------|-------|-------|----------|
| P5-01 | Metricas sem user_id label + 13 metricas audit | ALTA | #4, #6 | 026 rate_limit, 033 HMAC kid | 4 cap5 Cardinality | 30m | P8 |
| P5-02 | promtool check rules + prometheus.yml rule_files | MEDIA | #1 | 021 silent except | 4 cap10 Alerting | 20m | P8 |
| P5-03 | Grafana 11.1.0 dashboard JSON + p95 <300ms | MEDIA | #4, #6 | 028/029 policy | 4 cap11 Grafana, 6 cap8 | 40m | P8 |
| P5-04 | Alerts firing drill 6/6 (ConfigInvalid, ApiHighErrorRate, RateLimitDenialsHigh, KidLegacyHigh, MemoryLatencyHigh, ServiceDown) | ALTA | #1, #6 | 033 kid rotation | 4 cap6 Histograms, 4 cap10 | 45m | P8 |
| P5-05 | Audit log fallback drill + redact_pii antes de json.dumps | ALTA | #6 | 025 dual-write, 010 audit | 5 DDIA cap3, 3 cap13 | 25m | P8 |
| P5-06 | CI metrics job + /metrics endpoint + compose observability profile | MEDIA | #1-6 | — | 6 cap14 Testing, 4 cap5 | 20m | P8 |

Total 3h. Ordem: P5-01 -> P5-02 -> P5-06 (paralelo) -> P5-03 -> P5-04 -> P5-05

---

## 5. DETALHAMENTO P5-01..06 — ERRADO->CORRETO

### P5-01 — Metricas sem user_id (30m) — Axiom #4 + CIPHER-026/033 + Livro 4 cap5

Objetivo: Provar que NENHUMA metrica usa user_id como label. Prometheus cap5: cardinality = product of label values. user_id = infinito -> OOM.

ERRADO (antes P4, ainda possivel regressao):

    # src/jefrey/core/metrics.py — ERRADO
    RATE_LIMIT_TOTAL = Counter("jefrey_rate_limit_total", labelnames=["user_id","tool_name","decision"])  # user_id explode cardinalidade
    EVENTBUS_KID_LEGACY_TOTAL = Counter("jefrey_eventbus_kid_legacy_total", labelnames=["user_id"])

CORRETO (atual ja correto, P5 prova e trava):

    # src/jefrey/core/metrics.py — CORRETO (P4-02 fix mantido)
    RATE_LIMIT_TOTAL = Counter("jefrey_rate_limit_total", labelnames=["tool_name","decision"])  # sem user_id
    EVENTBUS_KID_LEGACY_TOTAL = Counter("jefrey_eventbus_kid_legacy_total", labelnames=[])  # sem label — global, cap5 OK
    CONFIG_VALID = Gauge("jefrey_config_valid", labelnames=[])  # 0/1
    MEMORY_LATENCY = Histogram("jefrey_memory_latency_seconds", labelnames=["le"])  # p50/p95 sem user_id
    # Grep que bloqueia regressao:
    # grep -rn 'labelnames.*user_id' src/ -> deve ser 0

Comando P5-01:

    grep -rn 'labelnames.*user_id' src/  # 0
    grep -rn 'user_id.*label' src/  # 0
    curl -s http://localhost:8000/metrics | grep jefrey_ | grep user_id  # 0 linhas
    python -m pytest tests/test_p4_policy_guest.py -v  # guest sem user_id ainda deny

Artefato: docs/METRICS_CARDINALITY.md 1 pg com lista 13 metricas + cardinalidade + promql sem user_id.

---

### P5-02 — promtool check rules (20m) — Axiom #1 + CIPHER-021 + Livro 4 cap10

Objetivo: rule_files carregado + sintaxe valida + for/labels corretos. Sem isso alerts nunca disparam (falso verde).

ERRADO:

    # docker/prometheus/prometheus.yml — ERRADO (antes P4-04)
    global:
      scrape_interval: 15s
      evaluation_interval: 15s
    # sem rule_files — alerts.yml existe mas nunca carregado
    # docker/prometheus/alerts.yml — ERRADO
    groups:
      - name: jefrey.slo
        rules:
          - alert: JefreyConfigInvalid
            expr: jefrey_config_valid == 0  # sem for, sem labels -> dispara flap

CORRETO (P4-04 ja correto, P5 prova com promtool):

    # docker/prometheus/prometheus.yml — CORRETO
    global:
      scrape_interval: 15s
      evaluation_interval: 15s
    rule_files:
      - /etc/prometheus/alerts.yml  # cap10: rule_files obrigatorio
    # docker/prometheus/alerts.yml — CORRETO (6 regras com for/labels)
      - alert: JefreyConfigInvalid
        expr: jefrey_config_valid == 0
        for: 1m
        labels: {severity: critical, slo: config}
        annotations: {summary: "Jefrey config invalida", description: "CONFIG_VALID==0 ha 1m"}
    # docker-compose.yml volumes:
    # - ./docker/prometheus/alerts.yml:/etc/prometheus/alerts.yml:ro

Comando P5-02:

    docker run --rm -v "%cd%/docker/prometheus:/etc/prometheus" prom/prometheus:v2.53.0 promtool check rules /etc/prometheus/alerts.yml  # 0 errors
    docker run --rm -v "%cd%:/etc/prometheus" prom/prometheus:v2.53.0 promtool check config /etc/prometheus/docker/prometheus/prometheus.yml
    docker compose config -q  # com env dummy

Artefato: CI step promtool ja em .github/workflows/ci.yml (adicionar apos guard).

---

### P5-03 — Grafana dashboard (40m) — Axiom #4/#6 + Livro 4 cap11 + SWE cap8

Objetivo: Dashboard JSON versionado com 4 panels p95 HNSW, rate_limit deny ratio, kid legacy, config_valid. Screenshot prova p95 <300ms (SLO 1.2).

ERRADO:

    // grafana/dashboards/jefrey.json — ERRADO (nao existe, so prometheus+grafana sem dashboard)
    {
      "title": "Jefrey",
      "panels": []  // vazio ou com user_id template variable -> cardinalidade
    }

CORRETO:

    // docker/grafana/dashboards/jefrey-slo.json — CORRETO
    {
      "title": "JEFREY SLOs (P5)",
      "uid": "jefrey-slo",
      "panels": [
        {"title": "Memory p95 (HNSW)", "expr": "histogram_quantile(0.95, sum(rate(jefrey_memory_latency_seconds_bucket[5m])) by (le))", "threshold": 0.3},
        {"title": "RateLimit deny ratio", "expr": "sum(rate(jefrey_rate_limit_total{decision=deny}[5m])) / clamp_min(sum(rate(jefrey_rate_limit_total[5m])),1)"},
        {"title": "Kid Legacy /10m", "expr": "increase(jefrey_eventbus_kid_legacy_total[10m])"},
        {"title": "Config Valid", "expr": "jefrey_config_valid"}
      ]
    }
    # Mount: ./docker/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
    # Provisioning: ./docker/grafana/provisioning/dashboards/jefrey.yml

Comando P5-03:

    docker compose --profile observability up -d prometheus grafana
    curl -s http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(jefrey_memory_latency_seconds_bucket[5m]))%20by%20(le))
    # screenshot grafana http://localhost:3000/d/jefrey-slo -> docs/screenshots/grafana-p95.png

Artefato: docker/grafana/dashboards/jefrey-slo.json + provisioning + doc screenshot.

---

### P5-04 — Alerts firing drill 6/6 (45m) — Axiom #1/#6 + CIPHER-033 + Livro 4 cap6/10

Objetivo: Provar que cada alert REALMENTE dispara. Falso verde: arquivo existe mas expr nunca true.

ERRADO:

    # Drill falso: so checar arquivo existe
    test -f docker/prometheus/alerts.yml && echo PASS  # nao prova firing
    # KidLegacyHigh nunca dispara porque ninguem envia msg v0

CORRETO:

    # scripts/drill_alerts.py — CORRETO (forca cada condicao)
    # 1. JefreyConfigInvalid: set JEFREY_CONFIG_VALID=0 -> http://prometheus:9090/api/v1/alerts -> firing 1m
    # 2. JefreyKidLegacyHigh: publicar 11 msgs v0 (sem kid) -> increase(kid_legacy[10m]) >10 -> firing
    python scripts/drill_alerts.py --alert KidLegacyHigh --count 11  # usa signing sem kid + verify dual-try -> metric +1
    # 3. JefreyRateLimitDenialsHigh: forcar 100 req com deny >0.1% -> firing
    # 4. JefreyMemoryLatencyHigh: SET LOCAL hnsw.ef_search=200 + 100 queries -> p95>300ms
    # 5. JefreyApiHighErrorRate: injetar 2% tools_blocked -> firing
    # 6. JefreyServiceDown: docker stop jefrey-api -> up==0 -> firing
    curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.state=="firing")'

Comando P5-04:

    python scripts/drill_alerts.py --all  # 6 drills, cada um espera for 1m/5m
    curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[] | .name=="jefrey.slo"'
    # Evidencia: docs/screenshots/alerts-firing.json com 6 alerts firing

Artefato: scripts/drill_alerts.py + docs/screenshots/alerts-firing.json + update SLO_RUNBOOK 1.1 -> 1.2 com drill results.

---

### P5-05 — Audit fallback drill (25m) — Axiom #6 + CIPHER-025/010 + DDIA cap3 + Livro 3 cap13

Objetivo: Postgres down != perda de audit. Dual-write com redact_pii antes de json.dumps.

ERRADO:

    # src/jefrey/core/audit.py — ERRADO (antes)
    raw = json.dumps(record, ensure_ascii=False, default=str)  # sem redact -> vaza Bearer sk-xxx
    with open(path, "a") as f: f.write(raw)
    # sem logger.error no Postgres fail

CORRETO (ja correto P4, P5 prova drill):

    # src/jefrey/core/audit.py — CORRETO (P5 drill prova)
    detail_redacted = _redact_detail(detail)  # redact antes de persistir
    try:
        with get_db() as s: s.add(AuditLog(detail_json=dict(detail_redacted))); s.commit()
    except Exception as e:
        logger.error("audit: FALHA Postgres %s", type(e).__name__)  # CIPHER-021 nunca silent
        self._write_fallback(detail=detail_redacted, error=str(e))  # fallback
    def _write_fallback(...):
        raw = json.dumps(record, ensure_ascii=False, default=str)
        raw = redact_pii(raw)  # segunda camada antes de arquivo
        with open(path, "a", encoding="utf-8") as f: f.write(raw+"\n")
        logger.warning("audit: fallback gravado em %s", path)

Comando P5-05:

    docker compose stop postgres
    JEFREY_ENV=prod python -c "from src.jefrey.core.audit import audit_tool_call; audit_tool_call(thread_id='t1', tool_name='test', actor_role='user', risk='low', decision='allow', detail={'token':'Bearer abc123'})"
    cat $(grep -r audit_fallback_path src/jefrey/core/config.py | cut -d'=' -f2)  # deve conter [REDACTED] nao Bearer
    docker compose start postgres

Artefato: Teste pytest test_p5_audit_fallback.py + log redacted.

---

### P5-06 — CI metrics job (20m) — Axiom #1-6 + SWE cap14 + Livro 4 cap5

Objetivo: CI nao so guard+pytest mas tambem promtool + /metrics + compose.

ERRADO:

    # .github/workflows/ci.yml — ERRADO (P4)
      - name: Guard 6 greps
        run: bash scripts/guard_anti_patterns.sh
      - name: Pytest
        run: pytest tests -q
    # sem promtool, sem curl /metrics, sem compose observability

CORRETO:

    # .github/workflows/ci.yml — CORRETO P5 (add 3 steps apos guard)
          - name: Promtool check
            run: docker run --rm -v $(pwd)/docker/prometheus:/etc/prometheus prom/prometheus:v2.53.0 promtool check rules /etc/prometheus/alerts.yml
          - name: Metrics no user_id
            run: grep -rn 'labelnames.*user_id' src/ && exit 1 || echo "no user_id label OK"
          - name: Compose + metrics endpoint
            run: |
              docker compose up -d postgres redis jefrey-api
              sleep 10
              curl -sf http://localhost:8000/metrics | grep -q jefrey_config_valid
              curl -s http://localhost:8000/metrics | grep -q user_id && exit 1 || echo "metrics OK"

Comando P5-06:

    act -j guard-audit-pytest  # ou gh workflow run
    docker compose config -q && echo COMPOSE_OK

---

## 6. ORDEM DE EXECUCAO — 3h

| Ordem | ID | Cmd | Tempo | Commit |
|-------|----|-----|-------|--------|
| 1 | P5-01 | grep labelnames + curl /metrics + docs/METRICS_CARDINALITY.md | 30m | commit "P5-01 metrics cardinality (Livro4 cap5) + guard + pytest" |
| 2 | P5-02 | promtool + rule_files + ci promtool job | 20m | commit "P5-02 promtool check rules (Livro4 cap10)" |
| 3 | P5-06 | CI metrics job + compose | 20m | junto com P5-02 (paralelo) |
| 4 | P5-03 | Grafana dashboard JSON + provisioning | 40m | commit "P5-03 grafana slo dashboard (Livro4 cap11)" |
| 5 | P5-04 | drill_alerts.py 6 drills + screenshots | 45m | commit "P5-04 alerts firing 6/6 drill (Livro4 cap6)" |
| 6 | P5-05 | audit fallback drill + test | 25m | commit "P5-05 audit fallback redact drill (DDIA cap3)" |
| 7 | Final | _validate_deep 90/90 + _validate_full + compose + pytest 20 + promtool + curl /metrics | 10m | commit "P5-FINAL 100% + SLO_RUNBOOK 1.2" |

Regra: cada commit roda antes: guard 6/6 + audit prod 0 CRITICO + compileall + pytest + compose config -q (igual P4).

---

## 7. CHECKLIST QUE BLOQUEIA P8

- [ ] grep -rn 'labelnames.*user_id' src/ -> 0 (P5-01)
- [ ] curl -s /metrics | grep user_id -> 0 (P5-01)
- [ ] promtool check rules docker/prometheus/alerts.yml -> 0 errors (P5-02)
- [ ] docker/prometheus/prometheus.yml tem rule_files: - /etc/prometheus/alerts.yml (P5-02)
- [ ] docker/grafana/dashboards/jefrey-slo.json existe + 4 panels (P5-03)
- [ ] curl /api/v1/alerts com 6 firing apos drill (P5-04) — evidencia json
- [ ] audit fallback contem [REDACTED] nao Bearer (P5-05)
- [ ] ci.yml tem jobs promtool + metrics (P5-06)
- [ ] _validate_deep.py 90/90 100% + _validate_full.py 20 passed + guard 6/6 + compose OK
- [ ] SLO_RUNBOOK.md 1.1 -> 1.2 com drill results + THREAT_MODEL.md sem mudanca

---

## 8. RISCOS / ROLLBACK

| Risco | Mitigacao |
|-------|-----------|
| Grafana sem dados (HNSW sem carga) | P5-03 usa ef_search 200 drill para gerar p95 |
| promtool image nao baixa em CI | fallback: pip install prometheus-client + cache docker |
| user_id regressao | guard extra grep labelnames.*user_id no pre-commit + ci |
| Firing drill demora 5m for | usar for: 30s em teste com promtool test rules |

Rollback: git revert HEAD por P5-xx; alerts e dashboard sao mount :ro, sem migracao DB.

---

## 9. ARTEFATOS P5

- docs/METRICS_CARDINALITY.md
- docker/grafana/dashboards/jefrey-slo.json + provisioning
- scripts/drill_alerts.py
- tests/test_p5_audit_fallback.py + tests/test_p5_metrics_cardinality.py
- docs/screenshots/grafana-p95.png + alerts-firing.json
- .github/workflows/ci.yml (+ promtool + metrics)
- SLO_RUNBOOK.md 1.2 FINAL

---

## 10. PROXIMO APOS P5 — P6 DATA (DDIA)

P6 (2h, DDIA cap5/6/12 + SWE cap8): psql d+ hnsw m16/ef64 CONCURRENTLY, SET LOCAL hnsw.ef_search bench 64 vs 200 (docs/HNSW_TUNING.md ja tem, falta prova d+), backup/restore drill, 2-processos XADD/XREADGROUP kid v1->v2 dual-verify (ja validado em _validate_full 8). So entao P8 tag v1.0.0-p5.

> P7 Perf (Livros 7,8) DEPOIS de P5/P6 estaveis — High Perf Python cap1-3 so com p95 real medido.

