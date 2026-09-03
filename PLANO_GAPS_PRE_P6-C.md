# PLANO GAPS PRE P6-C — Fechamento DATA antes de P6-C verify (40m)

> **Versão:** 1.0 — 2026-09-02 21:05 -03 | **Autor:** Staff Eng + Axiom/CIPHER + 10 Livros | **Estado entrada:** `d9dd5e0 feat(P6-B) 136/136` `38 passed` `compileall OK` `guard 6/6` `promtool 6/6` `Grafana 8 panels` `git clean`
> **Objetivo:** zerar TODO gap de P6 DATA deixado por P6-A/P6-B antes de abrir P6-C (`verify_p6_data.py` idempotente + deep 150/150). Sem este plano P6-C vira falso verde.
> **Duração:** 40 min (bloqueia P6-C 150/150 → P7/P8) | **Branch:** `master` | **Commit:** 1 único `feat(P6-C-pre): gaps DATA fechados + verify idempotente (144/144)` ou direto P6-C 150/150 (decidir no ato)
> **Gates:** `136/136 → 144/144` (este plano) → 150/150 (P6-C verify) | **Stack:** pgvector 0.5.1 dim768 + Redis 7.2 + Streams + kid v1/v2
> **Referências trancadas:** DDIA cap3/5/6/12 + SWE cap14 + Livro4 cap5 + CIPHER-033 + Axiom #1/#2/#6

---

## 0. DIRETRIZES TRANCADAS — Checklist Antes de CADA Commit (CONTRIBUTING.md §0)

**6 Princípios FAIL-CLOSED (copiar no PR description):**
1. **FAIL-CLOSED** — env ausente/inválida → `raise RuntimeError/ValueError`, nunca auto-key/fallback allow. Reprodução C1a: `JEFREY_ENV=prod JEFREY_EVENTBUS__HMAC_KEY= python -c "from src.jefrey.eventbus.signing import _get_hmac_key; _get_hmac_key()" → RuntimeError`
2. **ISOLAMENTO** — toda query/fila/cache/session DEVE filtrar `user_id` explícito. Default `user_id=None`, `user_role=guest`. Tenant A nunca lê dado de B.
3. **SEM STUB EM PROD** — `valid_`, `stub`, `placeholder` → se `JEFREY_ENV=prod` → `NotImplementedError` + grep 0 em src/ + docker-compose.yml
4. **PERSISTÊNCIA REAL** — nunca dict/list in-memory para revogação/token/broker. Use Redis TTL + pool_pre_ping + pool_recycle 3600
5. **CRIPTO CORRETA** — HMAC `kid+user_id.timestamp.canonical` sort_keys+separators + compare_digest + timezone.utc Z; JWKS urlsafe_b64encode sem padding + RS256+kid; JWT aud/iss/exp/kid/alg
6. **LEAST PRIVILEGE** — overwrite=False, .:/app:ro read_only tmpfs, CORS allowlist explicit, :?required para PASSWORD/SECRET

**6 Greps exatos (0 hits) — bash scripts/guard_anti_patterns.sh:**
```bash
grep -rn "dev-auto-generated-key" src/jefrey/eventbus/  # G1 C1a 0
grep -rn 'return "allow"' src/jefrey/core/rate_limit.py  # G2 C1b 0
grep -rn -E "except.*:[[:space:]]*pass" src/  # G3 0
grep -rn -E "str\(.*dict|str\(.*canonical|str\(.*payload" src/jefrey/eventbus/ src/jefrey/core/audit.py | grep -v "default=str"  # G4 0
grep -rn "b64encode" src/jefrey/oauth2/ | grep -v "urlsafe_b64encode"  # G5 0
grep -rn "overwrite=True" src/; grep -rn "valid_" src/jefrey/oauth2/; grep -rn -E '\\\$\\{JEFREY_[A-Z_]*PASSWORD:-[^}]*\\}' docker-compose.yml; grep -rn ".:/app" docker-compose.yml | grep -v ":ro"  # G6 0
```

**Livros deste plano:** DDIA cap3 Persistence + cap5 Replication + cap6 Partitioning + cap12 Tuning | SWE cap14 Testing | Livro4 cap5 Cardinality (gate, não regride)

---

## 1. ESTADO DE ENTRADA — Validado 2026-09-02 21:05 (d9dd5e0)

```
py_compile 2/2 OK (drill_streams, drill_audit) | compileall -q src RC0 | guard_anti_patterns 6/6 PASS | guard_grafana OK
json.tool jefrey.json 8 panels OK (schema39 uid jefrey-main editable false by(le)>=2)
yaml safe_load 8/8 OK (alerts 6 rules, alerts_test 6 groups alert_rule_test, prometheus rule_files, grafana ymls, ci 6 jobs, pre-commit, compose :ro)
promtool check rules 6 SUCCESS | promtool test rules 6/6 SUCCESS | compose config -q RC0 (com dummy ?required)
grep labelnames.*user_id 0 | REGISTRY colet 0 user_id (P5-01 travado)
pytest 38 passed (35+3 P6-B) 4 warnings | _validate_deep 136/136 100% WARNS0 BUGS0 (ainda sem seção U P6-B)
reports: p6-streams.log 1260B (XADD→XREADGROUP→XACK→DLQ→ISOLATION→KID v1/v2) + p6-backup.log 1282B (pg_dump+BGSAVE) + p6-hnsw-proof.log 6578B + p6-bench.log 8813B + p5-04-drill.log 4386B + p5-05-drill.log 758B
git clean master d9dd5e0 > e8266f6 > 1621c46 | working tree clean
```

**O que P6-A/P6-B ENTREGARAM (DONE):**
- P6-A: schema.py AUTOCOMMIT + 4x CONCURRENTLY IF NOT EXISTS WITH (m='16', ef_construction='64') + models.py 5 hnsw + bench ef64 vs 200 (Seq Scan correto p/ 101 rows) + docs/HNSW_TUNING.md 88L + proof logs
- P6-B: drill_streams_two_processes.py 165L XADD maxlen10000 approximate + xgroup_create mkstream BUSYGROUP + XREADGROUP jefrey-workers > + XACK pending0 + DLQ jefrey:dlq:{user_id} maxlen5000 + kid rotation HMAC_KEYS_JSON v1/v2 dual-verify + DeprecationWarning v0 + EVENTBUS_KID_LEGACY_TOTAL [] + isolation u-stream vs u-stream2 + backup pg_dump --no-owner + BGSAVE + tests 3/3

**O que FALTA (única fonte de verdade):**

| ID | Severidade | Achado | Impacto se não fechar | Estado | Livro |
|----|------------|--------|----------------------|--------|-------|
| **G-P6-06** | **ALTA** | `scripts/verify_p6_data.py` idempotente **não existe**; `scripts/verify_p6.py` atual é stub observabilidade antigo (6 panels) copiado de P6-observability, não cobre DATA → falso verde | `verify_p6.py` roda mas não prova HNSW/CONCURRENTLY/Streams/DLQ/kid/backup → CI passa sem DATA | **OPEN** | SWE cap14, DDIA |
| **G-P6-05** | **ALTA** | `tests/test_p6_isolation.py` 2 tenants **não existe**; `pg_memory.py _build_filter user_id mandatory` nunca provado com `u-A vs u-B zero leak` + pool_pre_ping sem teste de reconexão | Tenant A lê memória de B → viola Axiom #2; pool stale → OperationalError silencioso | **OPEN** | DDIA cap3, Axiom #2 |
| **G-P6-04b** | **MÉDIA** | `_validate_deep.py` ainda em **136/136**; seção **U P6-B** (8 gates: hnsw m16/ef64/vector_cosine_ops/\d+ proof/CONCURRENTLY/EXPLAIN note/bench 64 vs 200/pool_pre_ping/pool_recycle/isolation/backup/streams 2proc/DLQ/kid dual/xgroup_create/maxlen) **não adicionada**; commit d9dd5e0 anuncia 144/144 mas deep não reflete → divergência log vs gate | Gate mente: CI/LLM acha 144 mas deep valida 136 → falso verde se alguém confiar no log | **OPEN** | SWE cap14 |
| **G-P6-03b** | **MÉDIA** | `scripts/backup_restore.sh` / drill backup **só via python inline**; sem script idempotente versionado + sem gate CI que garante `audit_fallback.jsonl` durability | Restauração não reproduzível; DDIA cap5 durabilidade não travada em CI | **OPEN** | DDIA cap5 |
| **G-OPS-01** | **BAIXA** | `jefrey-api / jefrey-mcp Restarting (1)` + `jefrey-redis (unhealthy)` NOAUTH vs Ready — não bloqueia drill (usa password URL) mas **bloqueia P8 deploy** healthcheck | P8 `docker compose up -d --wait healthy` falha → tag sem runtime saudável | **OPEN (não bloqueia P6-C, bloqueia P8)** | Axiom #6 |
| **G-HYGIENE** | **BAIXA** | Temp files `_tmp_*.py` removidos no d9dd5e0? Verificar `git status --porcelain` limpo, mas garantir `_p6*.py` / `_tmp_full_validate.py` não ressurgiram | Sujeira → diff ruído + guard falha | **CHECK** | SWE cap8 Style |
| **G-CARD** | **BAIXA** | Regressão cardinality: P6-B não tocou metrics, mas `verify_p6_data.py` futuro **não deve** introduzir `labelnames.*user_id` | Se regride, derruba P5-01 (800 séries vs 8M OOM) | **GATE** | Livro4 cap5 |

Sem fechar G-P6-06 + G-P6-05 + G-P6-04b, P6-C (verify) não tem o que verificar. Ordem axiomática: fechar DATA → depois P7 perf (HPP/Fluent) → depois P8 tag.

---

## 2. VEREDITO PESSIMISTA → OTIMISTA

| Visão | % prod-ready | Gate | Evidência |
|-------|--------------|------|-----------|
| **Pessimista (hoje)** | 97% código, 85% DATA provado | 136/136 sintático, infra viva mas sem verify idempotente | deep 136/136 ≠ 144/144 prometido; isolation só manual no drill, sem pytest 2 tenants; verify_p6.py stub |
| **Otimista (após este plano)** | 99% DATA provado | 144/144 com U + verify_p6_data idempotente + isolation pytest | deep U 8 gates + verify reproduzível sem rede mockada + backup idempotente |
| **P8 liberado após** | 99%+ | 150/150 (P6-C) → 162/162 (P8) | + tag v1.0.0-p5 + CHANGELOG + compose healthy + IdP real |

**P6-A/P6-B entregaram infra viva; este plano entrega a LENTE que prova que ela não regride.**

---

## 3. INVENTÁRIO — 5 Sub-tarefas (40m)

| ID | Sub-tarefa | Tempo | Artefato | Gate |
|----|------------|-------|----------|------|
| **C1** | Audit gaps: `verify_p6.py` vs `verify_p6_data.py` + deep diff + reports hygiene | 5m | este plano §1 | — |
| **C2** | `scripts/verify_p6_data.py` idempotente (DDIA cap3/5/6/12, SWE cap14): checa CONCURRENTLY IF NOT EXISTS + m16/ef64/vector_cosine_ops + \d+ prova + bench note + pool_pre_ping/pool_recycle + isolation + streams maxlen/xgroup/DLQ/kid dual + backup files | 15m | scripts/verify_p6_data.py 180L | +5 gates |
| **C3** | `tests/test_p6_isolation.py` 2 tenants (Axiom #2): u-A vs u-B zero leak em pg_memory + redis Streams topic isolation | 10m | tests/test_p6_isolation.py 90L 2 tests | +2 gates |
| **C4** | `scripts/_validate_deep.py` seção **U P6-B** 144/144 (+8 gates) + fix divergência 136→144 | 5m | scripts/_validate_deep.py 553L | 136→144 |
| **C5** | Re-validação full + commit único: compileall + guard 6/6 + grafana 8 panels + yaml 8/8 + promtool 6/6 + pytest 40 (38+2) + deep 144/144 + compose config -q + git add -f reports | 5m | commit feat(P6-C-pre) ou feat(P6) 144/144 | 144/144 |

Total 40m. P6-C (verify 150/150) vem DEPOIS, consome 15m extra (não neste plano).

---

## 4. SPECS ERRADO→CORRETO

### C2 — verify_p6_data.py (o buraco central)

**ERRADO (atual):** `scripts/verify_p6.py` 194L checa "metrics.py existe / Grafana 6 panels / prometheus.yml jefrey-api:8000" — é P6-observability antigo, não DATA. Roda verde mesmo se HNSW não existir.

**CORRETO (DDIA cap3/12 + SWE cap14):**
```python
# scripts/verify_p6_data.py — idempotente, sem rede mockada, ASCII
# - lê src/jefrey/core/schema.py: assert CONCURRENTLY IF NOT EXISTS + m='16' + ef_construction='64' + AUTOCOMMIT
# - lê src/jefrey/core/models.py: 5x hnsw m16 ef64 vector_cosine_ops + ix_user_created + ix_approvals_user_thread
# - lê src/jefrey/core/db.py: pool_pre_ping True + pool_recycle 3600
# - lê src/jefrey/core/pg_memory.py: _build_filter user_id mandatory (table.user_id == user_id)
# - lê docs/HNSW_TUNING.md: bench ef 64 vs 200 + nota Seq Scan 101 rows
# - lê scripts/bench_hnsw.py: CAST(:emb AS vector) + SET LOCAL f-string int(ef)
# - lê src/jefrey/eventbus/signing.py: HMAC_KEYS_JSON dual-verify + DeprecationWarning v0 + EVENTBUS_KID_LEGACY_TOTAL []
# - lê src/jefrey/eventbus/publisher.py: XADD maxlen 10000 approximate + topic jefrey.events.{user_id}.{tool_name}
# - lê src/jefrey/eventbus/subscriber.py: xgroup_create mkstream BUSYGROUP + xreadgroup + XACK + DLQ jefrey:dlq:{user_id} maxlen 5000
# - lê reports/p6-hnsw-proof.log: \d+ hnsw m16 ef64 + pg_indexes + vector 0.5.1
# - lê reports/p6-bench.log: p50/p95 ambos < SLO 300ms
# - lê reports/p6-streams.log: XADD→XREADGROUP→XACK→DLQ→ISOLATION→KID v1/v2
# - lê reports/p6-backup.log: pg_dump CREATE TABLE + BGSAVE + audit_fallback exists
# Exit 0 se tudo OK, 1 se gap → usado em CI e pre-commit
```
Idempotente: roda 2x sem duplicar índice (IF NOT EXISTS) e sem falhar se reports ausentes (warn, não bug, quando --offline).

### C3 — test_p6_isolation.py

**ERRADO:** sem teste; isolation só provado manualmente no drill_streams (u-stream vs u-stream2) — não roda em CI.

**CORRETO (Axiom #2, DDIA cap6):**
```python
def test_pg_memory_isolation_two_tenants(monkeypatch):
    # mock get_db com dict, mas _build_filter deve conter user_id == "u-A" e nunca retornar row de u-B
    # assert _build_filter(table, {}, user_id="u-A") contém clause user_id == "u-A"
    # + teste negativo: add com u-A não visível para search com u-B

def test_streams_topic_isolation():
    # assert topic builder jefrey.events.{user_id}.{tool} != jefrey.events.{other}.{tool}
    # + DLQ per user_id jefrey:dlq:{user_id} ≠ jefrey:dlq:{other}
```
Sem Redis vivo (CI unit): testa builders/filters, não XADD. Drill vivo já cobre XADD/XREADGROUP.

### C4 — _validate_deep.py U P6-B

**ERRADO:** 513L, só até T (P5-06), 136/136. Commit log fala 144/144 → divergência.

**CORRETO:**
```python
# --- U. P6-B streams 2-processos + backup + HNSW proof (DDIA cap5/6/12, CIPHER-033) ---
try:
    if "CONCURRENTLY IF NOT EXISTS" in read("src/jefrey/core/schema.py") and "m='16'" in ...: oks.append("P6-B schema CONCURRENTLY m16 ef64 OK")
    if "vector_cosine_ops" in read("src/jefrey/core/models.py"): oks.append("P6-B models hnsw vector_cosine_ops OK")
    if "pool_pre_ping" in read("src/jefrey/core/db.py") and "pool_recycle" in read("src/jefrey/core/db.py"): oks.append("P6-B db pool pre_ping+recycle OK")
    if "user_id == user_id" in read("src/jefrey/core/pg_memory.py") or "table.user_id ==" in ...: oks.append("P6-B pg_memory isolation OK")
    if "maxlen" in read("src/jefrey/eventbus/publisher.py") and "10000" in ...: oks.append("P6-B publisher maxlen 10000 OK")
    if "xgroup_create" in read("src/jefrey/eventbus/subscriber.py") and "mkstream" in ...: oks.append("P6-B subscriber xgroup mkstream OK")
    if "jefrey:dlq" in read("src/jefrey/eventbus/subscriber.py") and "maxlen=5000" in ...: oks.append("P6-B DLQ per-tenant OK")
    if "HMAC_KEYS_JSON" in read("src/jefrey/eventbus/signing.py") and "DeprecationWarning" in ...: oks.append("P6-B kid rotation v1/v2 + v0 warn OK")
    # + checks de reports existirem (warn se ausente, bug se schema errado)
except...
total_gates = len(oks)+len(bugs)+len(warns)  # agora 144
```
8 oks novos → 136+8=144. P6-C adicionará +6 → 150.

### C5 — Re-validação (gate que bloqueia commit)

```bash
python -m compileall -q src  # RC0
bash scripts/guard_anti_patterns.sh  # 6/6 PASS
python -m json.tool docker/grafana/dashboards/jefrey.json > /dev/null  # 8 panels
python -c "import yaml; [yaml.safe_load(open(f)) for f in ['docker/prometheus/alerts.yml','docker/prometheus/tests/alerts_test.yml','docker/prometheus/prometheus.yml','docker/grafana/provisioning/datasources/datasource.yml','docker/grafana/provisioning/dashboards/dashboard.yml','.github/workflows/ci.yml','.pre-commit-config.yaml','docker-compose.yml']]; print('yaml 8/8 OK')"
grep -rn 'labelnames.*user_id' src/ && exit 1 || echo "cardinality OK"
docker run --rm --entrypoint promtool -v .../docker/prometheus:/etc/prometheus prom/prometheus:v2.53.0 check rules /etc/prometheus/alerts.yml
docker run --rm --entrypoint promtool -v .../docker/prometheus:/etc/prometheus prom/prometheus:v2.53.0 test rules /etc/prometheus/tests/alerts_test.yml  # 6/6
python -m pytest tests -q  # 40 passed (38+2)
python scripts/_validate_deep.py  # 144/144
python scripts/verify_p6_data.py  # RC0 idempotente, 2ª rodada igual
docker compose config -q  # RC0 com dummy env
```

---

## 5. CHECKLIST BLOQUEIA P6-C

- [ ] C2 verify_p6_data.py py_compile OK + 2 rodadas idempotentes RC0
- [ ] C3 test_p6_isolation.py 2/2 passed, sem user_id label, sem network
- [ ] C4 _validate_deep.py 144/144 (U com 8 gates) — print FINAL OKS 144 WARNS 0 BUGS 0
- [ ] C5 full revalidação acima 100% + git status --porcelain clean (reports add -f) + 1 commit único
- [ ] Nenhum novo warn CARDINALITY, nenhum overwrite=True, nenhum :?required quebrado

---

## 6. RISCOS

| Risco | Mitigação |
|-------|-----------|
| verify_p6_data.py vira verify_p6.py duplicado | Manter verify_p6.py legado (observability) intacto; novo arquivo é verify_p6_data.py DATA — não sobrescrever |
| Deep U quebra string f / SyntaxError (histórico 3x) | Usar marker total_gates = len(oks) fora de f-string, não print("\nWARNS:") dentro de replace |
| Teste isolation precisa Postgres vivo e falha em CI | Testar _build_filter unit sem DB (mock table), não XADD vivo — drill vivo já cobre |
| Commit sem add -f reports | git add -f reports/p6-*.log obrigatório (reports/.gitignore) |

---

## 7. PRÓXIMOS PASSOS (fora deste plano, só após 144/144)

**P6-C (15m, SWE cap14):** `verify_p6_data.py` em CI job + pre-commit hook + deep 144→150 (+6 gates backup/bench/pool/isolation/streams/DLQ/kid) + docs/HNSW_TUNING §2 final + compose healthy fix (api/mcp Restarting + redis NOAUTH) + tag interna `p6-data-done`
**P7 (60m, HPP/Fluent):** cProfile hot paths (ToolExecutor polling sleep2, json dumps) + WeakValueDictionary — não bloqueia tag, pode ir p/ v1.1.0
**P8 (60m, SWE cap11/14):** tag v1.0.0-p5 + CHANGELOG a partir de d9dd5e0/e8266f6/1621c46/21aaa79 + compose up -d --wait healthy + IdP real ADR-001

---

## 8. REFERÊNCIAS

- PLANO_UNIFICADO_P6_P7_P8_V1.0.md 738L (240m) — este plano é slice C (gaps) antes de P6-C
- PLANO_FASE_P6-B_STREAMS_BACKUP.md 25.9KB — base para U gates
- DDIA Kleppmann cap3 Persistence, cap5 Replication, cap6 Partitioning, cap12 Tuning
- SWE at Google cap8 Style, cap14 Testing (verify idempotente)
- Livro4 Prometheus cap5 Cardinality (gate no user_id)
- CIPHER-033 HMAC kid v1/v2 dual-verify + EVENTBUS_KID_LEGACY_TOTAL []
- Axiom #1 FAIL-CLOSED, #2 ISOLAMENTO, #6 OBSERVABILIDADE, #7 PROD READY

> **Regra axiomática:** sem 144/144 não abrir P6-C 150/150. Sem 150/150 não abrir P7/P8.
