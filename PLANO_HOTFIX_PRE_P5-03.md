# PLANO HOTFIX PRE-P5.03 — Correção de Bugs Pendentes (P0→P5)

> **Versão:** 1.0 — 2026-09-02 12:23 -03:00  
> **Stack:** Python 3.14 runtime / 3.12 spec + FastAPI:8000 + Postgres16+pgvector + Redis7.2 + prometheus:v2.53.0 + grafana:11.1.0  
> **Princípios:** 6 Princípios FAIL-CLOSED + Axioms #1-#7 + CIPHER 021/026/031/033 + Livros 1,2,3 → 4,5,6 → 7,8,9,10  
> **Estado entrada:** P5-03a DONE parcial (docker-compose grafana read_only+tmpfs+provisioning:ro OK), hunt 12:23 achou **4 CRÍTICOS** + 1 desalinhamento que quebram prod  
> **Objetivo:** Zerar bugs pendentes com qualidade, sem bola de neve, gates 99/99 antes de avançar para P5.03b/c

---

## 1. Por que HOTFIX antes de P5-03b?

**Diretriz Axiom #1 (Observabilidade) + #7 (Idempotência) + CIPHER-021 (fail-closed) + Livro 6 cap14 (Testing):** não avançar com base quebrada. Hunt linha-a-linha p0→p5 (2026-09-02 12:23) revelou 4 bugs que **crasham container em prod** e desalinhamento Grafana que esconde SLO. Prosseguir sem fix = bola de neve (44=28+16 já mitigada). Este hotfix é **obrigatório** para manter 96-98% health e evitar falsos verdes (95/95 atual é falso verde pois `_validate_deep.py` não importa `mcp/server.py`).

---

## 2. Bugs Pendentes Mapeados (Hunt 12:23 linha-a-linha)

| ID | Severidade | Arquivo:Linha | Descrição | Axiom/CIPHER/Livro | Impacto prod |
|---|---|---|---|---|---|
| **CRIT-1** | 🔴 CRÍTICO | `src/jefrey/mcp/server.py:27` | `NameError: name 'sys' is not defined` — `import sys` ausente, `_ROOT = Path(...)` usa `sys.path` | Axiom #6 FAIL-CLOSED, CIPHER-021, Livro 6 cap8 Style | `mcp-server` container crash no boot, health /health nunca sobe |
| **CRIT-2** | 🔴 CRÍTICO | `src/jefrey/mcp/server.py:74-77` | `_run_guarded` usa `ctx.user_id` e `tool_name` **antes** de `ctx = PolicyContext(...)` — `NameError: ctx/tool_name not defined` + ordem lógica invertida | Axiom #2 Isolamento, #6 FAIL-CLOSED, CIPHER-026 Rate Limit, Livro 6 cap14 | Toda chamada tool via MCP retorna 500, PolicyEngine nunca executa |
| **CRIT-3** | 🔴 CRÍTICO | `src/jefrey/core/db.py:16` vs `src/jefrey/core/models.py:26` vs `src/jefrey/core/schema.py:8` | **Duplicate `Base`**: `db.py: Base = declarative_base()` (oauth2_clients) vs `models.py: class Base(DeclarativeBase)` (memory/approvals/audit) — `schema.py:init_db()` só faz `models.Base.metadata.create_all()` → `oauth2_clients` **nunca criada** | Axiom #2 Isolamento, CIPHER-031 OAuth, Livro 5 DDIA cap3 Persistence | `auth_middleware` falha ao validar client_id, introspect quebra em prod sem tabela |
| **CRIT-4** | 🟠 ALTO | `docker/grafana/dashboards/jefrey.json` | **6 panels desalinhados** vs 8 SLO + PromQL sem `sum by(le)` (Livro 4 cap6) + `editable:true` viola least privilege | Axiom #1 Observabilidade, #4 Least Privilege, Livro 4 cap11 Grafana, cap6 Histograms, cap5 Cardinality | Dashboard não reflete alerts.yml (ConfigInvalid, ApiHighErrorRate, RateLimitDenialsHigh, KidLegacyHigh, MemoryLatencyHigh, ServiceDown) — SLO invisível |
| **B1** | 🟡 MÉDIO | `docker/grafana/provisioning/datasources/datasource.yml` | Falta `orgId:1` + `httpMethod: POST` + `jsonData` incompleto — Grafana provisioning pode falhar silencioso em clean boot | Livro 4 cap11, Axiom #7 | Datasource não carrega após `docker compose down -v` |
| **B2** | 🟡 MÉDIO | `docker/grafana/provisioning/dashboards/dashboard.yml` | `editable:true` + `updateIntervalSeconds:30` vs 10s + falta validação `yaml.safe_load` em CI | Axiom #4, Livro 4 cap11 | Dashboard editável em prod permite drift, intervalo desalinhado com refresh 10s |
| **B3** | 🟡 MÉDIO | `.github/workflows/ci.yml` + `.pre-commit-config.yaml` | Sem job `grafana-lint` (json.tool + yaml safe_load + !grep user_id + grep sum by(le)) | Livro 6 cap14, Axiom #1 | CI não pega regressão de cardinalidade/high histogram |

**Nota:** P5-03a já corrigiu B1-compose (read_only:true + tmpfs /tmp + provisioning:ro + dashboards:/var/lib/grafana/dashboards:ro distinto de volume) — **mantido**. Restante acima é pendente.

---

## 3. Referências Axiom / CIPHER / Livros

| Ref | Aplicação neste hotfix |
|---|---|
| **Axiom #1 Observabilidade** | 8 panels SLO-alinhados, histogram_quantile com `sum by(le)`, alerts 6/6 visíveis |
| **Axiom #2 Isolamento** | PolicyContext user_id=None → guest fail-closed, rate-limit por thread_id surrogate |
| **Axiom #4 Least Privilege** | `editable:false`, `read_only:true`, `:ro` mounts, `allow_credentials:false` |
| **Axiom #6 FAIL-CLOSED** | `import sys` fix, RuntimeError em prod sem HMAC, deny se Redis falha (não allow) |
| **Axiom #7 Idempotência** | `CREATE TABLE IF NOT EXISTS`, `create_all` dual Base, provisioning yaml valid |
| **CIPHER-021 silent except** | `except Exception as e: logger.exception` não `pass` |
| **CIPHER-026 rate limiting** | `RateLimiter().is_allowed(thread_id, tool.name)` com try RuntimeError → deny |
| **CIPHER-031 OAuth2 JWKS** | Dual Base garante `oauth2_clients` existe para introspect |
| **CIPHER-033 HMAC** | kid versionado já OK, não tocado neste hotfix |
| **Livro 4 cap11 Grafana** | Provisioning datasources.yml + dashboards/dashboard.yml + 8 panels + uid jefrey-main schemaVersion 39 |
| **Livro 4 cap6 Histograms** | `histogram_quantile(0.95, sum(rate(..._bucket[5m])) by (le))` — SEMPRE sum by(le) |
| **Livro 4 cap5 Cardinality** | `grep -rn 'labelnames.*user_id' src/` → 0, `curl /metrics | grep user_id` → 0 |
| **Livro 6 cap14 Testing** | pytest 23 → 27 com test_p5_grafana_dashboards.py 4 tests, guard 6/6, compileall |

---

## 4. Plano Completo — 5 Sub-tarefas (45m total)

> **Ordem obrigatória:** HOTFIX CRIT-1/2/3 → P5-03b provisioning → P5-03c dashboard 8 panels → P5-03d CI lint → P5-03e gates 99/99 + commit único  
> **Regra:** Sem commit isolado por sub-tarefa — **commit único** ao final 99/99 (PLANO_FASE_P5_OBSERVABILITY), evita desync guards.

### 4.1 HOTFIX CRIT-1/2/3 (15m) — `src/jefrey/mcp/server.py` + `src/jefrey/core/schema.py`

#### ERRADO → CORRETO — CRIT-1 `import sys`

```python
# ERRADO — src/jefrey/mcp/server.py:15-28
import os
import types
import typing
import logging
import asyncio
from src.jefrey.core.rate_limit import RateLimiter
import contextvars
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:  # NameError: name 'sys' is not defined
    sys.path.insert(0, str(_ROOT))

# CORRETO — Axiom #6, Livro 6 cap8 Style (imports no topo, explícitos)
import sys  # <-- FIX CRIT-1
import os
import types
import typing
import logging
import asyncio
import contextvars
import json
from pathlib import Path

from src.jefrey.core.rate_limit import RateLimiter

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
```

#### ERRADO → CORRETO — CRIT-2 `_run_guarded` ordem + RateLimiter args + fail-closed

```python
# ERRADO — src/jefrey/mcp/server.py:69-78 (ordem invertida, variáveis não definidas)
async def _run_guarded(tool: StructuredTool, args: dict, thread_id: str) -> str:
    from src.jefrey.core.policy import get_policy_engine, PolicyContext, Decision
    from src.jefrey.core.registry import register_default_tools

    policy = get_policy_engine()
    # CIPHER-026: Rate limiting check
    _rl_dec = await RateLimiter().is_allowed(ctx.user_id, tool_name)  # BUG: ctx/tool_name não existem
    if _rl_dec == "deny":
        return f"[RATE LIMITED] thread={thread_id}"
    ctx = PolicyContext(thread_id=thread_id, user_role=_resolve_role(), autonomous=policy.autonomous)
    res = policy.decide(tool.name, args, ctx)

# CORRETO — Axiom #2 + CIPHER-026 + fail-closed (thread_id como surrogate user_id)
async def _run_guarded(tool: StructuredTool, args: dict, thread_id: str) -> str:
    """Aplica PolicyEngine (thread_id vindo do request) e executa a ferramenta se permitido."""
    from src.jefrey.core.policy import get_policy_engine, PolicyContext, Decision
    from src.jefrey.core.registry import register_default_tools

    policy = get_policy_engine()
    # CIPHER-026: ctx ANTES do rate-limit, thread_id como surrogate user_id (Axiom #2)
    ctx = PolicyContext(thread_id=thread_id, user_role=_resolve_role(), autonomous=policy.autonomous)
    # Rate limit fail-closed: try → deny se Redis falhar (nunca allow)
    try:
        _rl_dec = await RateLimiter().is_allowed(thread_id, tool.name)
    except RuntimeError as _e:
        logger.warning("rate limit check falhou (fail-closed deny): %s", _e)
        return f"[RATE LIMITED] thread={thread_id} (rate limiter unavailable)"
    if _rl_dec == "deny":
        return f"[RATE LIMITED] thread={thread_id}"
    res = policy.decide(tool.name, args, ctx)
    policy.audit(tool.name, res, ctx)
```

**Por que `thread_id` como `user_id`?** `PolicyContext` exige `user_id` para isolamento multi-tenant (Axiom #2). No MCP Gateway não há `user_id` HTTP — thread_id é o identificador do workflow n8n que chamou, usado como surrogate para rate-limit por workflow (evita `user_id=None` → guest deny em todo tool call). Discussão: alternativa `ctx.user_id = thread_id` explícito se modelo exigir, mas `is_allowed(thread_id, tool.name)` já isola por thread.

#### ERRADO → CORRETO — CRIT-3 `schema.py` dual Base

```python
# ERRADO — src/jefrey/core/schema.py:1-13
from sqlalchemy import text
from src.jefrey.core.db import get_engine
from src.jefrey.core.models import Base, MEMORY_TABLES

def init_db() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)  # BUG: só cria memory/approvals/audit, NÃO oauth2_clients

# CORRETO — Livro 5 DDIA cap3 Persistence + CIPHER-031 (duas Bases, uma init)
"""Inicialização do schema (extension + tabelas + índices HNSW)."""
from sqlalchemy import text
from src.jefrey.core.db import get_engine, Base as DbBase  # oauth2_clients
from src.jefrey.core.models import Base as ModelsBase, MEMORY_TABLES

def init_db() -> None:
    """Cria extension vector, tabelas e índices HNSW de similaridade coseno."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    # Cria AMBAS as Bases — idempotente, sem CONCURRENTLY em transação
    ModelsBase.metadata.create_all(engine)
    DbBase.metadata.create_all(engine)
    # ... restante igual (expires_at, metadata_json jsonb, hnsw indexes) ...
```

**Alternativa considerada:** mover `Oauth2Client` para `models.py` (single Base). Rejeitada: `db.py` já é importado por `config`/`get_engine`, mover geraria ciclo. Dual `create_all` é idiomático SQLAlchemy quando Bases são separadas por domínio (DDIA cap3).

**Gates HOTFIX:**
- `python -m py_compile src/jefrey/mcp/server.py` → OK (sem NameError)
- `python -m compileall -q src` → OK
- `python -c "from src.jefrey.mcp.server import build_server; print('import OK')"` → import OK (sem sys error)
- `pytest tests -q` → 23 passed (antes de P5-03c) → 27 após

---

### 4.2 P5-03b (5m) — Provisioning YAMLs `datasource.yml` + `dashboard.yml`

#### ERRADO → CORRETO — `docker/grafana/provisioning/datasources/datasource.yml`

```yaml
# ERRADO — atual 227B, falta orgId/httpMethod, pode falhar em clean boot
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    uid: PBFA97CFB590B2093
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      timeInterval: "15s"

# CORRETO — Livro 4 cap11 p. 284 (provisioning datasource), Axiom #7
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
      queryTimeout: "60s"
```

#### ERRADO → CORRETO — `docker/grafana/provisioning/dashboards/dashboard.yml`

```yaml
# ERRADO — atual editable:true + 30s desalinhado com refresh 10s
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
      foldersFromFilesStructure: false

# CORRETO — Axiom #4 Least Privilege + Livro 4 cap11
apiVersion: 1
providers:
  - name: "Jefrey"
    orgId: 1
    folder: "Jefrey"
    type: file
    disableDeletion: false
    editable: false          # least privilege: dashboard versionado em git, não editável em prod
    allowUiUpdates: false    # complementa editable:false (Grafana 11)
    updateIntervalSeconds: 10  # alinhado com dashboard refresh 10s
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: false
```

**Gate:** `python -c "import yaml, pathlib; yaml.safe_load(open('docker/grafana/provisioning/datasources/datasource.yml')); yaml.safe_load(open('docker/grafana/provisioning/dashboards/dashboard.yml')); print('yaml OK')"` → yaml OK

---

### 4.3 P5-03c (20m) — Rewrite `docker/grafana/dashboards/jefrey.json` 8 panels SLO-alinhados

**Mapeamento alerts.yml (6 alerts) → 8 panels (6 SLO + 2 oper limit):**

| Panel | Título | PromQL (CORRETO `sum by(le)`) | Alert coberto | Tipo |
|---|---|---|---|---|
| 1 | Config Valid | `jefrey_config_valid` | JefreyConfigInvalid | stat |
| 2 | Service Up | `up{job="jefrey-api"} == 1` / `jefrey_service_health` | JefreyServiceDown | stat |
| 3 | API Error Rate (5m) | `sum(rate(jefrey_http_requests_total{status=~"5.."}[5m])) / sum(rate(jefrey_http_requests_total[5m]))` | JefreyApiHighErrorRate >0.01 | timeseries |
| 4 | RateLimit Deny Rate | `sum(rate(jefrey_rate_limit_total{decision="deny"}[5m]))` | JefreyRateLimitDenialsHigh | timeseries |
| 5 | Memory p95 Latency | `histogram_quantile(0.95, sum(rate(jefrey_memory_latency_seconds_bucket[5m])) by (le))` | JefreyMemoryLatencyHigh >0.3 | timeseries |
| 6 | Kid Legacy (10m) | `sum(increase(jefrey_eventbus_kid_legacy_total[10m]))` | JefreyKidLegacyHigh >10 | stat |
| 7 | Tools Blocked (1h) | `sum by (tool_name) (increase(jefrey_tools_blocked_total[1h]))` | Oper limit | barchart |
| 8 | Approvals HITL (1h) | `increase(jefrey_approvals_created_total[1h])` + `increase(jefrey_approvals_decided_total[1h])` | Oper limit | barchart |

**ERRADO → CORRETO — PromQL histogram (Livro 4 cap6 p. 132: SEMPRE `sum by(le)` antes de quantile)**

```json
// ERRADO — atual jefrey.json panels 1 e 6
"expr": "histogram_quantile(0.50, rate(jefrey_llm_latency_seconds_bucket[5m]))"
"expr": "histogram_quantile(0.95, rate(jefrey_mcp_latency_seconds_bucket[5m]))"
// BUG: sem sum by(le) → quantile calcula por série individual, valor errado; sem operação filter

// CORRETO — Livro 4 cap6 + SLO MemoryLatencyHigh
"expr": "histogram_quantile(0.95, sum(rate(jefrey_memory_latency_seconds_bucket[5m])) by (le))"
// Para LLM P95/P99 (se manter):
"expr": "histogram_quantile(0.95, sum(rate(jefrey_llm_latency_seconds_bucket[5m])) by (le))"
```

**Outros fixes `jefrey.json`:**
- `editable: true` → `editable: false` (Axiom #4)
- `schemaVersion: 39` já OK, `uid: "jefrey-main"` já OK, `refresh: "10s"` já OK
- Adicionar `version: 2` (incrementa em cada rewrite)
- `grep -rn 'labelnames.*user_id' src/` → 0 já OK, mas novo painel não deve reintroduzir `user_id` label
- `grep 'sum by(le)' docker/grafana/dashboards/jefrey.json` → >=2 hits (memory + llm/mcp)

**Template 8 panels (resumo, arquivo completo no commit):** manter estrutura datasource `PBFA97CFB590B2093`, gridPos 2 linhas x 4 cols (w 6 cada) para 6 SLO stats + 2 oper barcharts.

---

### 4.4 P5-03d (5m) — CI `grafana-lint` job + pre-commit hooks

#### ERRADO → CORRETO — `.github/workflows/ci.yml`

```yaml
# ERRADO — atual sem grafana-lint, sem cardinalidade check
  guard-audit-pytest:
    steps:
      - name: promtool check rules
        run: docker run --rm --entrypoint promtool -v ${{ github.workspace }}/docker/prometheus:/etc/prometheus prom/prometheus:v2.53.0 check rules /etc/prometheus/alerts.yml
      - name: Guard 6 greps

# CORRETO — Livro 6 cap14 CI + Livro 4 cap5/6
  guard-audit-pytest:
    steps:
      - name: promtool check rules
        run: docker run --rm --entrypoint promtool -v ${{ github.workspace }}/docker/prometheus:/etc/prometheus prom/prometheus:v2.53.0 check rules /etc/prometheus/alerts.yml
      - name: promtool check config
        run: docker run --rm --entrypoint promtool -v ${{ github.workspace }}/docker/prometheus:/etc/prometheus prom/prometheus:v2.53.0 check config /etc/prometheus/prometheus.yml
      - name: grafana-lint (json valid + yaml safe_load + no user_id + sum by(le))
        run: |
          python -m json.tool docker/grafana/dashboards/jefrey.json > /dev/null && echo "grafana json OK"
          python -c "import yaml; yaml.safe_load(open('docker/grafana/provisioning/datasources/datasource.yml')); yaml.safe_load(open('docker/grafana/provisioning/dashboards/dashboard.yml')); print('grafana yaml OK')"
          bash -c 'grep -rn "labelnames.*user_id" src/ && echo "FAIL user_id label" && exit 1 || echo "metrics cardinality OK (0 user_id labels)"'
          bash -c 'grep -q "sum by(le)" docker/grafana/dashboards/jefrey.json && echo "histogram sum by(le) OK" || { echo "FAIL PromQL missing sum by(le)"; exit 1; }'
          bash -c 'grep -q "\"editable\": false" docker/grafana/dashboards/jefrey.json && echo "grafana editable false OK" || { echo "FAIL editable not false"; exit 1; }'
      - name: Guard 6 greps (fail-closed)
```

#### ERRADO → CORRETO — `.pre-commit-config.yaml`

```yaml
# ERRADO — sem grafana hooks
  - id: metrics-no-user-id
    entry: bash -c 'grep -rn labelnames.*user_id src/ && exit 1 || exit 0'

# CORRETO — adiciona 2 hooks locais grafana
      - id: grafana-json-lint
        name: grafana dashboard json valid + editable false + sum by(le)
        entry: bash -c 'python -m json.tool docker/grafana/dashboards/jefrey.json > /dev/null && grep -q "\"editable\": false" docker/grafana/dashboards/jefrey.json && grep -q "sum by(le)" docker/grafana/dashboards/jefrey.json || { echo "grafana dashboard lint FAIL"; exit 1; }'
        language: system
        files: ^docker/grafana/dashboards/jefrey\.json$
        pass_filenames: false
      - id: grafana-yaml-lint
        name: grafana provisioning yaml safe_load
        entry: bash -c 'python -c "import yaml; yaml.safe_load(open(\"docker/grafana/provisioning/datasources/datasource.yml\")); yaml.safe_load(open(\"docker/grafana/provisioning/dashboards/dashboard.yml\"))"'
        language: system
        files: ^docker/grafana/provisioning/.*\.yml$
        pass_filenames: false
```

---

### 4.5 P5-03e (5m) — Deep gate Q 99/99 + pytest 27 + guard + compose + commit único

**Novo gate Q em `scripts/_validate_deep.py` (99/99):**

- Q1: `import sys` em `mcp/server.py`
- Q2: `_run_guarded` ctx antes de RateLimiter + `thread_id, tool.name` args
- Q3: `schema.py` dual Base (`DbBase.metadata.create_all` + `ModelsBase.metadata.create_all`)
- Q4: `datasource.yml` has `orgId: 1` + `httpMethod`
- Q5: `dashboard.yml` `editable:false` + `allowUiUpdates:false` + `updateIntervalSeconds:10`
- Q6: `jefrey.json` 8 panels + `editable:false` + `uid:jefrey-main` + `schemaVersion:39` + `sum by(le) >=2` + `grep user_id 0`
- Q7: CI `grafana-lint` present + pre-commit grafana hooks
- (mantém 92 anteriores → 92+7 = 99)

**Novo teste `tests/test_p5_grafana_dashboards.py` (4 tests):**

1. `test_datasource_yaml_valid` — yaml.safe_load + orgId 1 + uid PBFA97CFB590B2093
2. `test_dashboard_yaml_valid` — yaml.safe_load + editable false + updateInterval 10
3. `test_dashboard_json_8_panels` — json load + 8 panels + editable false + sum by(le) >=2 + no user_id
4. `test_compose_grafana_mounts` — compose has `read_only:true` + `:ro` + `tmpfs /tmp` + distinct dashboards path

**Gates finais (ordem):**
1. `python -m py_compile src/jefrey/mcp/server.py src/jefrey/core/schema.py`
2. `python -m compileall -q src`
3. `python -c "from src.jefrey.mcp.server import build_server"` (import smoke)
4. `bash scripts/guard_anti_patterns.sh` → 6/6 PASS
5. `python -m json.tool docker/grafana/dashboards/jefrey.json` → OK
6. `python -c "import yaml; yaml.safe_load(...)"` → yaml OK
7. `docker run --rm --entrypoint promtool -v ... prom/prometheus:v2.53.0 check rules /etc/prometheus/alerts.yml` → 6 rules OK
8. `docker run ... check config /etc/prometheus/prometheus.yml` → OK
9. `JEFREY_EVENTBUS__HMAC_KEY=dummy32chars12345678901234 JEFREY_DATABASE__PASSWORD=dummy REDIS_PASSWORD=dummy GRAFANA_PASSWORD=dummy docker compose config -q` → COMPOSE_OK
10. `pytest tests -q` → 27 passed (23 + 4 grafana)
11. `python scripts/_validate_deep.py` → 99/99 100% (Q 99/99)
12. `git commit -m "fix(P5-03a-hotfix): mcp sys+ctx order + schema dual Base + grafana 8 panels (Livro4 cap11, 99/99)"`

---

## 5. Ordem de Execução e Dependências

```
HOTFIX CRIT-1/2/3 (15m) ──┐
                         ├──> P5-03b provisioning (5m) ──> P5-03c dashboard 8 panels (20m) ──> P5-03d CI lint (5m) ──> P5-03e gates 99/99 + commit (5m)
                         │
                         └──> (paralelo seguro: P5-03b não depende de HOTFIX, mas commit único exige HOTFIX primeiro)
```

**Tempo total:** 15+5+20+5+5 = 50m (40m P5-03 + 10m hotfix). Se paralelo b: 45m.

**Checklist bloqueia P5-04:**
- [ ] `grep -rn 'labelnames.*user_id' src/` → 0
- [ ] `curl -s localhost:8000/metrics | grep user_id` → 0 (em compose up)
- [ ] `grep -c '"title"' docker/grafana/dashboards/jefrey.json` → 8
- [ ] `grep -c 'sum by(le)' docker/grafana/dashboards/jefrey.json` → >=2
- [ ] `grep '"editable": false' docker/grafana/dashboards/jefrey.json` → 1
- [ ] `python scripts/_validate_deep.py` → 99/99
- [ ] `pytest tests -q` → 27 passed
- [ ] `docker compose config -q` → OK

---

## 6. Riscos e Mitigação Qualidade (sem bola de neve)

| Risco | Mitigação |
|---|---|
| **Import sys quebrar outro import** | `import sys` no topo, antes de `Path`, sem `sys.path` mutation fora de `if` |
| **RateLimiter thread_id vs user_id isolamento** | `thread_id` é tenant do workflow n8n; se futuro exigir user_id real, `PolicyContext(user_id=thread_id)` explícito + ADR |
| **Dual Base criar tabelas fora de ordem** | `create_all` idempotente, sem `IF NOT EXISTS` manual; ordem Models→Db não importa (sem FK entre) |
| **Dashboard 8 panels quebrar Grafana 11** | `schemaVersion:39` compatível Grafana 11.1.0, `uid` estável, `datasource uid` PBFA97CFB590B2093 já provisionado |
| **PromQL sum by(le) cardinalidade** | `by(le)` mantém cardinalidade baixa (12 buckets), não adiciona label `user_id` |
| **CI grafana-lint falhar em dev sem docker** | `promtool` step usa `docker run --rm --entrypoint promtool` (mesmo padrão P5-02), fallback `echo skip` apenas se docker ausente |
| **Falso verde _validate_deep 95/95** | Novo gate Q cobre mcp/server.py import + ctx order + dual Base — hunt anterior não cobria, agora 99/99 |

---

## 7. Commit

```
fix(P5-03a-hotfix): mcp sys+ctx order + schema dual Base + grafana 8 panels (Livro4 cap11, 99/99)

- CRIT-1: src/jefrey/mcp/server.py import sys (NameError boot)
- CRIT-2: _run_guarded ctx=PolicyContext antes RateLimiter, is_allowed(thread_id, tool.name) + try RuntimeError fail-closed (CIPHER-026, Axiom #2)
- CRIT-3: src/jefrey/core/schema.py dual Base (DbBase+ModelsBase) create_all — oauth2_clients agora criada (CIPHER-031, DDIA cap3)
- P5-03b: provisioning datasources/datasource.yml orgId:1 httpMethod POST + dashboards/dashboard.yml editable:false allowUiUpdates:false updateInterval 10s
- P5-03c: docker/grafana/dashboards/jefrey.json 8 panels SLO (ConfigValid, ServiceUp, ErrorRate, RateLimitDeny, Memory p95 sum by(le), KidLegacy, ToolsBlocked, Approvals) editable:false
- P5-03d: ci.yml grafana-lint job + pre-commit grafana-json/yaml-lint (Livro6 cap14)
- P5-03e: _validate_deep 95/95 -> 99/99 + tests/test_p5_grafana_dashboards.py 4 tests -> pytest 27 passed + guard 6/6 + promtool 6 rules + compose -q

Refs: Axiom #1 #2 #4 #6 #7, CIPHER-021/026/031/033, Livro4 cap5/6/11, Livro5 cap3, Livro6 cap14
```

---

*Gerado 2026-09-02 12:23 — hunt p0→p5 linha-a-linha, pronto para execução com calma/constância/qualidade, gates antes de commit.*
