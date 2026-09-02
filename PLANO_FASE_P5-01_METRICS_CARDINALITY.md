# PLANO FASE P5-01 — METRICS CARDINALITY (sem user_id)
Version: 1.0 — DRAFT 2026-09-02 — Sub-fase de P5 OBSERVABILITY
Base: PLANO_FASE_P5_OBSERVABILITY.md 1.0, PLANO_MESTRE_44_ISSUES.md v1.1, SLO_RUNBOOK 1.1 FINAL, THREAT_MODEL 1.1 FINAL, ADR-001 kid rotation
Estado entrada: P4-FINAL 67fc89d — compileall 0 + guard 6/6 PASS + pytest 20 passed + _validate_deep 90/90 100% + compose config -q OK + audit prod 0 CRITICO + git limpo (95-98% prod-ready codigo). P4-04 ja entrega alerts.yml 6 + rule_files + ci + HNSW m16/ef64.
Objetivo P5-01: Provar que NENHUMA metrica usa user_id como label (cardinalidade infinita). Gerar docs/METRICS_CARDINALITY.md com 13 metricas + testes + grep bloqueando regressao. Bloqueia P8 deploy. Duracao 30m.

---

## 1. VEREDITO PESSIMISTA -> OTIMISTA

| Visao | Gate | % |
|-------|------|---|
| Pessimista (hoje) | Codigo metricas ja correto (P4-02 sem user_id) mas sem prova: nenhum grep em CI, nenhum curl /metrics documentado, nenhum doc de cardinalidade | 95-98% |
| Otimista (apos P5-01 DONE) | + grep labelnames user_id = 0 em pre-commit+CI + curl /metrics sem user_id + docs/METRICS_CARDINALITY.md 13 linhas + test_p5_metrics_cardinality.py verde + _validate_deep 91/91 | 96-98% |
| P8 liberado | So apos P5-01..06 + P6 (DDIA) | 97-99% |

Sem P5-01, P8 faz deploy com risco de OOM Prometheus (Livro 4 cap5: cardinality = produto das cardinalidades dos labels). user_id = infinito.

---

## 2. 6 PRINCIPIOS FAIL-CLOSED + CIPHER + LIVROS — MAPEAMENTO P5-01

### 2.1 Principios
1. FAIL-CLOSED — prod sem secret = RuntimeError (C1a). P5-01 roda audit prod com dummy e deve passar so com secrets completos.
2. ISOLAMENTO (Axiom #2) — user_id=None guest least-privilege. Metrica NUNCA usa user_id; isolamento ja provado em policy.py user_id None deny.
3. SEM STUB EM PROD — valid_ stub so fora de prod + kid legacy so via DeprecationWarning + metric global sem label.
4. LEAST PRIVILEGE (Axiom #5 & #4) — P5-01 e o coracao: labelnames sem user_id = menor privilegio de cardinalidade.
5. PERSISTENCIA REAL — nao se aplica direto, mas metricas contam XADD maxlen 10000 e DLQ sem user_id.
6. CRIPTO CORRETA — kid sem user_id no label; kid versionado via HMAC_KEYS_JSON dual-verify.

### 2.2 CIPHER
- CIPHER-026 rate limiting — RATE_LIMIT_TOTAL deve ser por tool_name + decision (allow/deny/HITL), nunca por user_id. Prova: grep + test.
- CIPHER-033 HMAC-SHA256 EventBus — EVENTBUS_KID_LEGACY_TOTAL labelnames=[] global, sem user_id. Kid rotation ADR-001.
- CIPHER-021 silent except — nunca silenciar falha de metrica; logger.error se falhar.
- CIPHER-010 audit — audit logs tem user_id, mas metricas NAO (separacao forense vs observabilidade).

### 2.3 Livros — REFERENCES_MAPPING.md
- LIVRO 4 Prometheus Up & Running 2nd (Julien Pivotto) — CAP 5 CARDINALITY (secao Label Cardinality, When to use labels): P5-01 inteiro. Cap 5 diz: alta cardinalidade (user_id, email, request_id) mata Prometheus (TSDB explode).
- LIVRO 4 cap 6 Histograms — MEMORY_LATENCY histogram sem user_id, buckets le.
- LIVRO 6 SWE at Google cap 8 Style + cap 14 Testing — codigo limpo + testes deterministicos (monkeypatch, importlib.reload).
- LIVRO 10 Pragmatic Programmer cap 3 (DRY) — nao duplicar metrica por user.
- LIVRO 5 DDIA cap 12 (nao usado aqui) — reservado para P5-04 p95.
- LIVROS 1,2,3 ja aplicados em P1-P4; 7,8,9,10 DEPOIS (perf) — Axiom #1 proibe otimizar antes de provar cardinalidade.

---

## 3. INVENTARIO P5-01 — 5 SUB-TAREFAS (30m)

| ID | Tarefa | Severidade | Axiom/CIPHER/Livro | Tempo | Arquivo |
|----|--------|------------|------------------|-------|---------|
| P5-01a | Grep regressao labelnames user_id = 0 + pre-commit hook | ALTA | #4 / 026,033 / 4 cap5 | 5m | scripts/guard_anti_patterns.sh EXTRA + .pre-commit-config.yaml |
| P5-01b | Auditoria 13 metricas src/jefrey/core/metrics.py (lista + cardinalidade) | ALTA | #4 / 026,033 / 4 cap5 | 5m | docs/METRICS_CARDINALITY.md |
| P5-01c | Prova curl /metrics sem user_id (staging ou api local) | ALTA | #4 / — / 4 cap5 | 5m | tests/test_p5_metrics_cardinality.py + docs/screenshots |
| P5-01d | Teste pytest bloqueando regressao (grep em codigo + metrica sem user_id) | MEDIA | #4 / 026 / 6 cap14 | 10m | tests/test_p5_metrics_cardinality.py (3 tests) |
| P5-01e | CI job metrics no user_id + compose metrics endpoint | MEDIA | #1-6 / — / 6 cap14 | 5m | .github/workflows/ci.yml |

Total 30m. Ordem: a -> b -> d -> c -> e (c precisa api rodando).

---

## 4. DETALHAMENTO ERRADO->CORRETO

### 4.1 metrics.py — labelnames sem user_id (P5-01a/b)

ERRADO (hipotetico, quebraria Livro 4 cap5):
    RATE_LIMIT_TOTAL = Counter("jefrey_rate_limit_total", "Limitacoes", labelnames=["user_id","tool_name","decision"])
    # user_id = milhares de valores distintos -> cardinalidade infinita -> Prometheus OOM
    EVENTBUS_KID_LEGACY_TOTAL = Counter("jefrey_eventbus_kid_legacy_total", labelnames=["user_id"])
    TOOL_EXEC_TOTAL = Counter("jefrey_tool_exec_total", labelnames=["user_id","tool_name"])

CORRETO (atual P4-02, P5-01 trava com grep):
    RATE_LIMIT_TOTAL = Counter("jefrey_rate_limit_total", "Limitacoes", labelnames=["tool_name","decision"])
    # decision so tem 3 valores: allow/deny/hitl -> cardinalidade baixa (tool_name ~40, decision 3 => 120 series) CAP5 OK
    EVENTBUS_KID_LEGACY_TOTAL = Counter("jefrey_eventbus_kid_legacy_total", "Msgs sem kid", labelnames=[])
    # sem label = 1 serie global, usado so para alert KidLegacyHigh increase[10m]>10
    CONFIG_VALID = Gauge("jefrey_config_valid", "0/1", labelnames=[])
    MEMORY_LATENCY = Histogram("jefrey_memory_latency_seconds", "HNSW", labelnames=["operation"], buckets=[0.01,0.05,0.1,0.3,0.5,1.0])
    # operation = search/add (2 valores) -> 2 series x buckets -> cap6 OK
    TOOLS_BLOCKED = Counter("jefrey_tools_blocked_total", labelnames=["tool_name","reason"])

Grep que bloqueia regressao (P5-01a):
    grep -rn 'labelnames.*user_id' src/  # deve ser 0
    grep -rn 'Counter.*user_id' src/  # deve ser 0
    grep -rn 'Histogram.*user_id' src/  # deve ser 0
    # Guard extra: scripts/guard_anti_patterns.sh [EXTRA] ja checa user_id label

### 4.2 auth_middleware / policy — USER_ID NAO VAI PARA METRICA

ERRADO:
    # src/jefrey/api/auth_middleware.py
    RATE_LIMIT_TOTAL.labels(user_id=user_id, tool_name=tool).inc()  # vaza PII + explode

CORRETO:
    # src/jefrey/core/rate_limit.py + api/metrics_endpoint.py
    RATE_LIMIT_TOTAL.labels(tool_name=tool_name, decision=decision).inc()
    # user_id so vai para AuditLog (forense) e Redis Streams topic jefrey.events.{user_id}.{tool} (isolamento), nunca para Prometheus label
    # Prova: curl -s http://localhost:8000/metrics | grep jefrey_ | grep user_id  # 0 linhas

### 4.3 config / metrics_endpoint — /metrics sem user_id

ERRADO:
    # src/jefrey/api/metrics_endpoint.py exporia ?user_id=xxx como label via query param
    @app.get("/metrics")
    def metrics(user_id: str = Query(None)):  # NUNCA
        return generate_latest(REGISTRY).decode()

CORRETO:
    @app.get("/metrics")
    def metrics():  # sem param, sem user_id
        return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
    # Prometheus scrape sem auth por IP allowlist, Grafana sem template variable user_id

---

## 5. ARTEFATO docs/METRICS_CARDINALITY.md (P5-01b) — TEMPLATE

Arquivo 1 pagina, 13 metricas atuais (levantar via grep jefrey_ em metrics.py):
    | Metrica | Tipo | Labels | Cardinalidade | PromQL exemplo sem user_id | SLO |
    |---------|------|--------|---------------|------------------------------|-----|
    | jefrey_config_valid | Gauge | (none) | 1 | jefrey_config_valid == 0 | ConfigInvalid |
    | jefrey_rate_limit_total | Counter | tool_name, decision | ~40*3=120 | sum(rate(jefrey_rate_limit_total{decision="deny"}[5m])) / clamp_min(sum(rate(jefrey_rate_limit_total[5m])),1) | RateLimitDenialsHigh |
    | jefrey_eventbus_kid_legacy_total | Counter | (none) | 1 | increase(jefrey_eventbus_kid_legacy_total[10m]) >10 | KidLegacyHigh |
    | jefrey_memory_latency_seconds | Histogram | operation, le | 2*6=12 | histogram_quantile(0.95, sum(rate(jefrey_memory_latency_seconds_bucket[5m])) by (le)) | MemoryLatencyHigh |
    | jefrey_tool_exec_total | Counter | tool_name, status | ~40*2=80 | sum(rate(jefrey_tool_exec_total[5m])) | — |
    | jefrey_tools_blocked_total | Counter | tool_name, reason | ~40*4=160 | sum(rate(jefrey_tools_blocked_total[5m])) / clamp_min(sum(rate(jefrey_tool_exec_total[5m])),1) | ApiHighErrorRate |
    | ... total 13, todas sem user_id, total series estimado <500 (cap5 OK) |

Nota cap5: se tivesse user_id com 10k usuarios, cada metrica multiplicaria por 10k => 500*10k = 5M series => OOM.
Comando para gerar:
    grep -rn 'Counter\|Gauge\|Histogram' src/jefrey/core/metrics.py
    curl -s http://localhost:8000/metrics | grep "^jefrey_" | cut -d'{' -f1 | sort -u

---

## 6. COMANDOS P5-01 (reproducao fail-closed)

Antes de cada commit (copiar de PLANO_FASE_P5_OBSERVABILITY.md checklist):
    bash scripts/guard_anti_patterns.sh  # 6/6 PASS + EXTRA user_id label 0
    grep -rn 'labelnames.*user_id' src/ && exit 1 || echo "no user_id label OK"
    grep -rn 'user_id.*label' src/ && exit 1 || echo "no user_id in label OK"
    python -m compileall -q src  # 0
    python -m pytest tests/test_p5_metrics_cardinality.py -v  # 3 passed
    python -m pytest tests -q  # 20+3 passed
    JEFREY_ENV=prod JEFREY_EVENTBUS__HMAC_KEY=a... JEFREY_OAUTH__AUD=jefrey ... python audit_pessimista.py | findstr CRITICO  # 0
    docker compose config -q  # com env dummy
    # staging probe (quando api rodando):
    curl -s http://localhost:8000/metrics | grep -c user_id  # 0
    curl -s http://localhost:8000/metrics | grep jefrey_ | head -n 20

---

## 7. TESTES tests/test_p5_metrics_cardinality.py (P5-01d) — 3 TESTS

1. test_no_user_id_label_in_code — rglob src/**/*.py, procura labelnames.*user_id => assert 0 hits (SWE cap14 isolation).
2. test_metrics_exposed_without_user_id — levanta FastAPI TestClient, GET /metrics, assert 'user_id' not in body, assert 'jefrey_config_valid' in body, assert 'jefrey_rate_limit_total' in body.
3. test_rate_limit_metric_no_user_id_label — chama rate_limit.is_allowed_sync 2x (allow+deny) + verifica RATE_LIMIT_TOTAL._metrics keys nao contem user_id; checa EVENTBUS_KID_LEGACY_TOTAL labelnames == [].

Todos usam monkeypatch + HMAC dummy + nao precisam Redis real (fallback memory).
Padrao Fluent Python cap19: dataclass/registry sem mutacao global.

---

## 8. CI + PRE-COMMIT (P5-01e)

ERRADO (.github/workflows/ci.yml antes P4):
    - name: Guard 6 greps
      run: bash scripts/guard_anti_patterns.sh
    # sem checagem user_id label

CORRETO (P5-01e):
    - name: Guard 6 greps (fail-closed)
      run: bash scripts/guard_anti_patterns.sh
    - name: Metrics cardinality — no user_id label
      run: |
        grep -rn 'labelnames.*user_id' src/ && exit 1 || echo "no user_id label OK"
        grep -rn 'user_id.*labelnames' src/ && exit 1 || echo "OK"
    - name: Metrics endpoint (no user_id)
      run: |
        docker compose up -d jefrey-api  # ou python -m pytest tests/test_p5_metrics_cardinality.py::test_metrics_exposed_without_user_id
        curl -sf http://localhost:8000/metrics | grep -q jefrey_config_valid

.pre-commit-config.yaml добавить:
    - id: metrics-no-user-id
      name: metrics no user_id label (Livro 4 cap5)
      entry: bash -c "grep -rn 'labelnames.*user_id' src/ && exit 1 || exit 0"
      language: system
      always_run: true

---

## 9. CHECKLIST QUE BLOQUEIA P5-02 (proximo)

- [ ] grep -rn 'labelnames.*user_id' src/ -> 0
- [ ] grep -rn 'user_id.*label' src/ -> 0
- [ ] curl -s /metrics | grep user_id -> 0 (ou TestClient)
- [ ] docs/METRICS_CARDINALITY.md existe + lista 13 metricas + cardinalidade <500 series + promql sem user_id
- [ ] tests/test_p5_metrics_cardinality.py 3 tests passed
- [ ] python -m pytest tests -q -> 23 passed (20 +3)
- [ ] guard_anti_patterns.sh 6/6 PASS + EXTRA 0
- [ ] _validate_deep.py 91/91 100% (adicionar gate P5-01) + _validate_full.py OK
- [ ] compose config -q OK + promtool check rules 0 errors (ja P4-04)
- [ ] ci.yml tem job metrics cardinality

---

## 10. RISCOS / ROLLBACK

| Risco | Mitigacao |
|-------|-----------|
| Metrica nova adicionada com user_id por engano | guard EXTRA + pre-commit bloqueia commit; ci falha em PR |
| /metrics vazio em dev (api nao sobe) | teste usa TestClient sem docker; curl so em staging |
| Falso verde: grep nao pega label via variavel | teste 3 verifica _metrics keys em runtime, nao so texto |
| .gitignore bloqueia docs/METRICS_CARDINALITY.md | .gitignore ja tem !PLANO_FASE_P5*.md, docs/ nao ignorado |

Rollback: git revert HEAD (so docs + teste, sem migracao DB, sem mount).

---

## 11. ORDEM E COMMITS

| Ordem | Cmd | Commit msg |
|-------|-----|------------|
| 1 | Criar docs/METRICS_CARDINALITY.md + grep proof | commit "P5-01a/b metrics cardinality doc (Livro 4 cap5)" |
| 2 | Criar tests/test_p5_metrics_cardinality.py 3 tests | commit "P5-01d tests metrics no user_id (SWE cap14)" |
| 3 | Patch ci.yml + pre-commit (metrics no user_id) | commit "P5-01e CI metrics cardinality guard" |
| 4 | Final validate: deep 91/91 + full + guard + pytest 23 + compose | commit "P5-01 FINAL 100% + ready P5-02" |

Regra antes de cada commit: guard 6/6 + audit prod 0 CRITICO + compileall + pytest + compose config -q (igual P4).

---

## 12. PROXIMO APOS P5-01 — P5-02 PROMTOOL

P5-02 (20m, Livro 4 cap10 Alerting): promtool check rules + prometheus.yml rule_files + ci promtool job. Pre-req: P5-01 100% (sem user_id). So entao P5-03 Grafana + P5-04 firing drill.