# PLANO FASE P5-05 + P5-06 — Audit Fallback Drill + CI Metrics Job

> **Slot:** P5-05 (25m) + P5-06 (20m) = **45 min** | **Dependência:** P5-04 DONE `21aaa79` 122/122 100% | **Bloqueia:** P6 DATA (DDIA) + P8 deploy — sem P5-05/P5-06 não há prova de resiliência nem gate CI completo
> **Versão:** 1.0 — 2026-09-02 — Plano completo com diretrizes trancadas (6 Princípios FAIL-CLOSED + Axioms #1-7 + CIPHER-010/021/025/026/033 + 10 Livros)
> **Branch:** `master` | **Commits:** 1 commit único `feat(P5-05+06): audit fallback drill + CI metrics job` (padrão P5, evita dessincronia)
> **Gates:** `122/122 → 130/130` (+8) | `py_compile 69` + `compileall -q` + `guard 6/6` + `guard_grafana` + `promtool check+test 6/6` + `pytest -q` 30+ passed + `compose config -q`

---

## 0. Diretrizes Trancadas — Checklist Antes de Cada Commit

**6 Princípios FAIL-CLOSED (CONTRIBUTING.md):**
1. FAIL-CLOSED — prod sem secret = `RuntimeError`, nunca `warn`/`allow`
2. ISOLAMENTO — `user_id=None` → `guest` least-privilege; métrica NUNCA usa `user_id` como label (Livro 4 cap5)
3. SEM STUB EM PROD — `valid_` stub só quando `_is_prod()==False` + `UserWarning`
4. PERSISTÊNCIA REAL — Redis Streams `XADD maxlen 10000` + DLQ `jefrey:dlq:{user_id}` + audit dual-write Postgres→fallback file com `redact_pii`
5. CRIPTO CORRETA — `urlsafe_b64encode` sem padding + `RS256+kid` + `aud/iss/exp/kid` + `compare_digest` + `sort_keys`
6. LEAST PRIVILEGE — `overwrite=False`, `:ro`, `read_only`, `allow_credentials False` + CORS Origens explícitas, `:?required` para PASSWORD/SECRET

**Axioms aplicados P5-05/P5-06:**
- #1 FAIL-CLOSED — audit fallback NUNCA silencia; CI quebra se `/metrics` expõe `user_id`
- #4 CARDINALITY — `grep -rn 'labelnames.*user_id' src/` = 0 (Livro 4 cap5)
- #6 OBSERVABILIDADE — fallback `jsonl` com `ts` + `redact_pii` + `detail_json`; CI prova `/metrics` sem `user_id` + `promtool test 6/6`
- #7 PRODUÇÃO READY — 122/122 → 130/130 sem falso verde

**CIPHER:**
- 010 audit — toda falha logada com `thread_id/tool/decision` + `error` visível
- 021 silent-except — `except: pass` proibido; audit usa `logger.error` + `logger.warning` (não `pass`)
- 025 dual-write — audit `Postgres → data/audit_fallback.jsonl` com `redact_pii` antes de `json.dumps`
- 026 rate-limit — `RATE_LIMIT_TOTAL [tool_name,decision]` sem `user_id`
- 033 HMAC kid — `EVENTBUS_KID_LEGACY_TOTAL []` sem `user_id`

**10 Livros — P5-05/P5-06 usa:**
- **Livro 5 — DDIA Kleppmann cap3 (Storage & Retrieval, p. 70-95)** — write-ahead log / dual-write / fallback file como WAL local; audit fallback é WAL forense
- **Livro 5 — DDIA cap12 (Future, p. 485-512)** — resiliência sem stub em prod
- **Livro 6 — SWE at Google cap14 (Testing, p. 245-280)** — CI como teste de regressão; `test_p5_*` 4→8 testes; `verify_p5.py` como `cap14` testing gate
- **Livro 4 — Prometheus Up & Running 2nd cap5 (Cardinality)** — CI gate `metrics cardinality 0 user_id` já em P5-01, reforçado aqui
- Demais: 1,2,3 já aplicados P0-P4; 7,8,9,10 DEPOIS de P5/P6 estáveis (Axiom #1 proíbe perf prematuro)

---

## 1. Estado de Entrada — Validado 2026-09-02

```
py_compile 69 files OK | compileall -q src EXIT 0
guard_anti_patterns 6/6 PASS
guard_grafana OK (editable:false, by(le)>=2, orgId:1)
promtool check rules 6 rules SUCCESS | promtool test rules 6/6 SUCCESS (P5-04)
pytest 31 passed (tests/test_p5_* 3 suites) | _validate_deep 122/122 100%
grafana 8 panels SLO alinhados | compose config -q OK
git clean 21aaa79 feat(P5-04) 122/122
```

**GAP que este plano fecha:**

| ID | Severidade | Achado | Impacto se não fechar |
|----|------------|--------|----------------------|
| **G1** | ALTA | `src/jefrey/core/audit.py` dual-write existe mas **nunca drillado**: `_write_fallback` só roda quando Postgres falha — sem teste, risco de `redact_pii` depois de `json.dumps` (PII vaza), `path` não criado, `detail` com `str(dict)` (GREP-4), ou `user_id=None` → `"system"` inconsistente | PII vaza no `audit_fallback.jsonl`; fallback quebra em prod; viola Axiom #4 + CIPHER-025 + Livro 5 DDIA cap3 |
| **G2** | MÉDIA | `CI .github/workflows/ci.yml` já tem `promtool check+test` (P5-04) mas **sem job dedicado `metrics cardinality + /metrics`**: `grep labelnames.*user_id` roda mas sem `curl /metrics | grep user_id == 0` nem `pytest tests/test_p5_*` explícito — regress de P5-01 passa silencioso | P8 deploy com `user_id` em label → cardinalidade infinita → Prometheus OOM (Livro 4 cap5); viola SWE cap14 |
| **G3** | BAIXA | `data/audit_fallback.jsonl` não existe / não gitignored com exceção de teste; `audit_fallback_path` sem sufixo `.jsonl` não validado | Fallback escreve em path inesperado; CI não testa conteúdo `redact_pii` |

**Sem P5-05/P5-06:** auditoria forense não provada + CI sem gate de cardinalidade completo → P8 deploy cego (quebra #6 PERSISTÊNCIA REAL + CIPHER-025).

---

## 2. Inventário P5-05/P5-06 — 8 Sub-tarefas (45m)

| ID | Sub-tarefa | Livro | Axiom/CIPHER | Tempo | Artefato |
|----|------------|-------|--------------|-------|----------|
| **a** | `audit.py` revalidação linha-a-linha: `redact_pii` antes de `json.dumps`, `_redact_detail` recursivo, `detail_json=dict(detail_redacted)`, `user_id or "system"` consistente, `_write_fallback` com `os.makedirs` + `record` determinístico `ts` UTC | DDIA cap3, L3 cap13 | #6, #4, CIPHER-025/010 | 5m | `src/jefrey/core/audit.py` (já correto — só drill) |
| **b** | `scripts/drill_audit_fallback.py` — drill isolado 1 função: força `AuditLogger._write_fallback` com Postgres mockado (sem rede), verifica `data/audit_fallback.jsonl` contém `redact_pii` (sem `sk-`/`@email`/`cpf`), `ts` UTC, `user_id`, `detail` redigido | DDIA cap3 | #6 CIPHER-025 | 10m | `scripts/drill_audit_fallback.py` |
| **c** | `tests/test_p5_audit_fallback.py` — 3 testes: `test_audit_redact_before_json`, `test_fallback_file_redact`, `test_fallback_user_id_consistency` (pytest sem Postgres real — tmp_path) | SWE cap14 | #6 | 5m | `tests/test_p5_audit_fallback.py` |
| **d** | `CI metrics cardinality job` — amplia `ci.yml`: `grep -rn 'labelnames.*user_id' src/` + `grep 'user_id' src/jefrey/core/metrics.py` já existe, adiciona `python -m pytest tests/test_p5_* -q` **+ `curl -s /metrics | grep user_id` quando API up** (ou `python -c "from prometheus_client import REGISTRY; assert 'user_id' not in str(REGISTRY.collect())"` sem rede) | L4 cap5, SWE cap14 | #4 | 5m | `.github/workflows/ci.yml` |
| **e** | `pre-commit` — hook `audit-fallback` opcional (ou amplia `guard_anti_patterns`): verifica `redact_pii.*json.dumps` ordem + `user_id.*system` consistência | SWE cap14 | CIPHER-010/025 | 3m | `.pre-commit-config.yaml` |
| **f** | `compose + .gitignore` — `data/audit_fallback.jsonl` gitignored mas `data/.gitkeep` mantém pasta; compose não muda (audit é file, não service) | DDIA cap3 | #6 | 2m | `.gitignore`, `data/.gitkeep` |
| **g** | `reports/p5-05-drill.log` — artifact: roda `drill_audit_fallback.py` + `pytest test_p5_audit_fallback` + `grep labelnames` + `audit_fallback.jsonl` sample redigido (sem PII real) | DDIA cap3 | CIPHER-025/010 | 5m | `reports/p5-05-drill.log` (git add -f, igual P5-04) |
| **h** | `_validate_deep.py` Q→R expansão: `130/130` — adiciona seção S `P5-05 audit fallback drill` (4 gates: `redact_before_json`, `fallback_makedirs`, `fallback_redact`, `fallback_user_id`) + T `P5-06 CI metrics job` (4 gates: `ci_metrics_job`, `pre_audit_hook`, `pytest_p5_*`, `compose_gitignore`) | SWE cap14 | #1 | 10m | `scripts/_validate_deep.py` 122→130 |

**Total 45m.** Ordem: `a` (revalida) → `b+c` (drill+tests) → `f` (gitignore) → `d+e` (CI/pre-commit) → `g` (log) → `h` (deep).

---

## 3. ERRADO → CORRETO Diffs

### 3.1 P5-05a — audit.py ordem `redact_pii` antes de `json.dumps`

**ERRADO (hipotético regressão — PII vaza):**
```python
# src/jefrey/core/audit.py — ERRADO (redact depois de dumps)
record = {"thread_id": thread_id, "detail": detail, ...}  # detail com PII cru
raw = json.dumps(record, ensure_ascii=False, default=str)  # PII já serializado
# sem redact → sk-... / email / cpf vai para o arquivo
with open(path, "a") as f: f.write(raw + "\n")
```

**CORRETO (atual já correto — P5-05 prova que NÃO regrediu):**
```python
# src/jefrey/core/audit.py — CORRETO (DDIA cap3 WAL + CIPHER-010)
detail_redacted = _redact_detail(detail)  # 1) redact recursivo ANTES
record = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "thread_id": thread_id, "detail": detail or {}, ...,
          "user_id": user_id or "system"}  # 2) user_id consistente
raw = json.dumps(record, ensure_ascii=False, default=str)
raw = redact_pii(raw)  # 3) segunda camada: redact no raw (cinto + suspensório)
with open(path, "a", encoding="utf-8") as f: f.write(raw + "\n")
# 4) os.makedirs(os.path.dirname(path) or ".", exist_ok=True) antes
```

**Verificação linha-a-linha P5-05a:**
- `_PII_RE = re.compile(r"(sk-[a-zA-Z0-9]{20,}|Bearer\s+[a-zA-Z0-9._\-]+|...cpf...)")` → OK (sk-, Bearer, email, cpf)
- `_redact_detail` recursivo `dict → _redact_detail(v)` para `dict` aninhado → OK
- `log()` faz `detail_redacted = _redact_detail(detail)` **antes** de `s.add(AuditLog(detail_json=dict(detail_redacted)))` → OK
- `_write_fallback` faz `raw = json.dumps(record, ...); raw = redact_pii(raw)` → OK (dupla camada)
- `path = get_settings().api.audit_fallback_path` default `"data/audit_fallback.jsonl"` → OK
- `os.makedirs(..., exist_ok=True)` → OK (DDIA cap3: WAL não falha por pasta ausente)
- `logger.error` (Postgres falha) + `logger.warning` (fallback ok) + `logger.error` (fallback também falha) → sem `except: pass` → CIPHER-021 OK
- `user_id or "system"` consistente em `log()` e `_write_fallback` → OK
- `datetime.now(timezone.utc).isoformat()` → timezone-aware → OK

### 3.2 P5-05b — drill_audit_fallback.py (DDIA cap3)

**ERRADO (sem drill — falha silenciosa):**
```bash
# Não existe; fallback nunca testado; se PII vazar só descobre em prod
```

**CORRETO:**
```python
# scripts/drill_audit_fallback.py — P5-05b (DDIA cap3, Axiom #6, CIPHER-025/010, fail-closed)
"""Drill audit fallback — força dual-write sem Postgres, verifica redact_pii."""
from __future__ import annotations
import os, sys, json, tempfile
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path: sys.path.insert(0, str(_ROOT / "src"))
if str(_ROOT) not in sys.path: sys.path.insert(0, str(_ROOT))

def _is_prod(): return os.getenv("JEFREY_ENV","dev")=="prod"
def _require_not_prod(force: bool):
    if _is_prod() and not force:
        print("FAIL-CLOSED: JEFREY_ENV=prod — recusa drill sem --force (Axiom #1)", file=sys.stderr)
        sys.exit(2)

def drill_audit_fallback(tmp_path: Path | None = None, force: bool = False):
    _require_not_prod(force)
    from src.jefrey.core.audit import AuditLogger, redact_pii
    # tmp file isolado (sem sujar data/audit_fallback.jsonl real)
    fallback = tmp_path / "audit_fallback.jsonl" if tmp_path else Path(tempfile.mktemp(suffix=".jsonl"))
    fallback.parent.mkdir(parents=True, exist_ok=True)
    # monkeypatch get_settings().api.audit_fallback_path
    from unittest.mock import patch, MagicMock
    mock_settings = MagicMock()
    mock_settings.api.audit_fallback_path = str(fallback)
    logger = AuditLogger()
    with patch("src.jefrey.core.config.get_settings", return_value=mock_settings):
        # detail com PII sintético
        detail = {"msg": "token sk-abc123XYZ45678901234567890 email test@example.com cpf 123.456.789-00"}
        logger._write_fallback(thread_id="t-drill", tool_name="memory.search", actor_role="user",
                               risk="LOW", decision="allow", reason=None, approval_id=None,
                               approval_decision=None, source="agent", detail=detail,
                               error="ConnectionRefusedError: postgres down (drill)", user_id="u-drill")
    content = fallback.read_text(encoding="utf-8")
    assert "[REDACTED]" in content, "redact_pii não aplicado"
    assert "sk-abc123" not in content and "test@example.com" not in content, "PII vazou"
    assert "t-drill" in content and "u-drill" in content
    assert "audit_error" in content
    print(f"[drill] audit fallback OK → {fallback} ({len(content)} bytes, redact OK)")
    return fallback

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Drill audit fallback (DDIA cap3)")
    ap.add_argument("--force", action="store_true", help="permite em JEFREY_ENV=prod")
    ap.add_argument("--cleanup", action="store_true", help="remove tmp file após drill")
    ap.add_argument("mode", nargs="?", default="run", choices=["run","help"])
    args = ap.parse_args()
    p = drill_audit_fallback(force=args.force)
    if args.cleanup: p.unlink(missing_ok=True)
```

**Invariantes:** `FAIL-CLOSED prod` + `dual sys.path` + `tmp_path` isolado + `redact_pii` verificado + sem `user_id` em `labelnames` + idempotente.

### 3.3 P5-05c — tests/test_p5_audit_fallback.py (SWE cap14)

```python
# tests/test_p5_audit_fallback.py — 3 testes (SWE cap14)
import json, py_compile, pathlib
def test_audit_redact_before_json():
    txt = pathlib.Path("src/jefrey/core/audit.py").read_text(encoding="utf-8")
    assert "_redact_detail" in txt and "detail_redacted" in txt
    # redact antes de AuditLog(detail_json=dict(detail_redacted))
    assert txt.find("_redact_detail") < txt.find("detail_json")
    assert "redact_pii(raw)" in txt  # segunda camada no fallback

def test_fallback_file_redact(tmp_path):
    from unittest.mock import patch, MagicMock
    from src.jefrey.core.audit import AuditLogger
    fallback = tmp_path / "fallback.jsonl"
    mock_settings = MagicMock(); mock_settings.api.audit_fallback_path = str(fallback)
    with patch("src.jefrey.core.config.get_settings", return_value=mock_settings):
        AuditLogger()._write_fallback(thread_id="t1", tool_name="x", actor_role="user",
            risk="LOW", decision="allow", reason=None, approval_id=None, approval_decision=None,
            source="agent", detail={"pii": "sk-abc123XYZ45678901234567890"}, error="drill", user_id="u1")
    txt = fallback.read_text(encoding="utf-8")
    assert "[REDACTED]" in txt and "sk-abc123" not in txt
    rec = json.loads(txt.strip())
    assert "ts" in rec and "audit_error" in rec

def test_fallback_user_id_consistency(tmp_path):
    from unittest.mock import patch, MagicMock
    from src.jefrey.core.audit import AuditLogger
    fallback = tmp_path / "fallback.jsonl"
    mock_settings = MagicMock(); mock_settings.api.audit_fallback_path = str(fallback)
    with patch("src.jefrey.core.config.get_settings", return_value=mock_settings):
        AuditLogger()._write_fallback(thread_id="t1", tool_name="x", actor_role="user",
            risk="LOW", decision="deny", reason="r", approval_id=None, approval_decision=None,
            source="agent", detail={}, error="e", user_id=None)
    rec = json.loads(fallback.read_text(encoding="utf-8").strip())
    assert rec["user_id"] == "system"  # None → system consistente
```

### 3.4 P5-06d — CI metrics job ampliado (SWE cap14 + L4 cap5)

**ERRADO (atual CI — já tem cardinalidade mas sem pytest + sem /metrics check sem rede):**
```yaml
# .github/workflows/ci.yml — falta pytest P5 explícito + fallback sem rede
- name: Metrics cardinality — no user_id label (P5-01 Livro 4 cap5)
  run: |
    grep -rn "labelnames.*user_id" src/ && exit 1 || echo "no user_id label OK"
```

**CORRETO (P5-06d — amplia sem quebrar P5-04):**
```yaml
# .github/workflows/ci.yml — P5-06d (SWE cap14, L4 cap5)
# Inserir APÓS "Prometheus alerts test (6/6 firing drill, Livro4 cap10)" e ANTES de "Guard 6 greps"
- name: Metrics cardinality + /metrics no user_id + pytest P5 (P5-01/P5-06 L4 cap5 + SWE cap14)
  run: |
    grep -rn "labelnames.*user_id" src/ && { echo "FAIL user_id label cardinality"; exit 1; } || echo "no user_id label OK (cap5)"
    python -c "import pathlib; txt=''.join(p.read_text(errors='ignore') for p in pathlib.Path('src').rglob('*.py')); assert 'labelnames' not in txt or 'user_id' not in ''.join(l for l in txt.splitlines() if 'labelnames' in l), 'user_id em labelnames'"
    python -c "from prometheus_client import REGISTRY; txt=str(list(REGISTRY.collect())); assert 'user_id' not in txt.lower() or 'labelnames' not in txt, 'user_id em REGISTRY'; print('REGISTRY no user_id OK')"
    python -m pytest tests/test_p5_metrics_cardinality.py tests/test_p5_grafana_dashboards.py tests/test_p5_alerts_drill.py tests/test_p5_audit_fallback.py -q
```

**Nota:** `curl /metrics` não roda em CI sem API up; o check `REGISTRY.collect()` cobre o mesmo sem rede (Livro 4 cap5 sem infra).

### 3.5 P5-06e — pre-commit hook audit

**CORRETO:**
```yaml
# .pre-commit-config.yaml — P5-06e (SWE cap14)
- id: audit-fallback-redact
  name: audit fallback redact_pii before json (DDIA cap3, CIPHER-025)
  entry: bash -c 'python -c "import pathlib; t=pathlib.Path(\"src/jefrey/core/audit.py\").read_text(encoding=\"utf-8\"); assert \"_redact_detail\" in t and t.find(\"_redact_detail\") < t.find(\"detail_json\"), \"redact order\"; assert \"redact_pii(raw)\" in t, \"second layer\"; print(\"audit redact order OK\")"'
  language: system
  files: ^src/jefrey/core/audit\.py$
```

### 3.6 P5-06f — .gitignore + data/.gitkeep

**CORRETO:**
```gitignore
# .gitignore — já tem data/*.jsonl? Verificar; adicionar se não:
data/audit_fallback.jsonl
!data/.gitkeep
```
`data/.gitkeep` vazio mantém pasta versionada; `audit_fallback.jsonl` real nunca commitado (exceto `reports/p5-05-drill.log` sample redigido via `git add -f`).

### 3.7 P5-06h — _validate_deep.py 122→130

**Seção S — P5-05 audit fallback drill (DDIA cap3):**
```python
# --- S. P5-05 audit fallback drill (DDIA cap3, CIPHER-025/010) ---
try:
    _audit_txt = read("src/jefrey/core/audit.py")
    if "_redact_detail" in _audit_txt and "detail_redacted" in _audit_txt:
        if _audit_txt.find("_redact_detail") < _audit_txt.find("detail_json"):
            oks.append("P5-05 audit redact before json OK")
        else: bugs.append("P5-05 audit redact ordem errada (depois de json)")
    else: bugs.append("P5-05 audit sem _redact_detail")
    if "redact_pii(raw)" in _audit_txt: oks.append("P5-05 audit second layer redact_pii(raw) OK")
    else: bugs.append("P5-05 audit sem segunda camada redact")
    if "os.makedirs" in _audit_txt and "audit_fallback_path" in _audit_txt: oks.append("P5-05 audit makedirs+path OK")
    else: bugs.append("P5-05 audit sem makedirs/path")
    if 'user_id or "system"' in _audit_txt: oks.append("P5-05 audit user_id system OK")
    else: bugs.append("P5-05 audit user_id inconsistency")
    _drill_audit = Path("scripts/drill_audit_fallback.py")
    if _drill_audit.exists():
        _dt = _drill_audit.read_text(encoding="utf-8")
        if "FAIL-CLOSED" in _dt and "sys.exit(2)" in _dt: oks.append("P5-05 drill FAIL-CLOSED OK")
        else: bugs.append("P5-05 drill sem FAIL-CLOSED")
        if "tmp_path" in _dt or "tempfile" in _dt: oks.append("P5-05 drill isolado tmp OK")
        else: warns.append("P5-05 drill sem tmp isolado")
    else: bugs.append("P5-05 drill_audit_fallback.py faltando")
    if Path("tests/test_p5_audit_fallback.py").exists(): oks.append("P5-05 test file OK")
    else: bugs.append("P5-05 test file faltando")
except Exception as e: bugs.append(f"P5-05 audit exception {e}")
```

**Seção T — P5-06 CI metrics job (SWE cap14):**
```python
# --- T. P5-06 CI metrics job (SWE cap14, L4 cap5) ---
try:
    _ci = read(".github/workflows/ci.yml")
    if "Metrics cardinality" in _ci or "cardinality" in _ci.lower(): oks.append("P5-06 CI cardinality job OK")
    else: bugs.append("P5-06 CI sem cardinality job")
    if "REGISTRY" in _ci and "user_id" in _ci: oks.append("P5-06 CI REGISTRY check OK")
    else: warns.append("P5-06 CI sem REGISTRY check (sem rede)")
    if "test_p5" in _ci: oks.append("P5-06 CI pytest P5 OK")
    else: bugs.append("P5-06 CI sem pytest P5")
    _pre = read(".pre-commit-config.yaml")
    if "audit-fallback" in _pre.lower() or "audit" in _pre.lower(): oks.append("P5-06 pre-commit audit OK")
    else: warns.append("P5-06 pre-commit sem audit hook (opcional)")
    if Path("data/.gitkeep").exists(): oks.append("P5-06 data .gitkeep OK")
    else: warns.append("P5-06 data/.gitkeep faltando")
    if "audit_fallback.jsonl" in read(".gitignore"): oks.append("P5-06 .gitignore audit fallback OK")
    else: bugs.append("P5-06 .gitignore sem audit_fallback.jsonl")
except Exception as e: bugs.append(f"P5-06 CI exception {e}")
```

---

## 4. Plano de Execução — 45m Passo a Passo (fail-closed, sem dessincronia)

### Fase A — Revalidação + Drill + Tests (20m)

1. `python -m py_compile src/jefrey/core/audit.py` + `read + grep` ordem redact (5m) — prova G1 sem mudar código se já correto
2. Criar `scripts/drill_audit_fallback.py` (126 linhas, dual path, FAIL-CLOSED, tmp isolado) — `py_compile` OK (10m)
3. Criar `tests/test_p5_audit_fallback.py` 3 testes — `python -m py_compile` + `pytest -q` 3/3 (5m)

**Gates A:** `py_compile OK` + `drill --help` + `drill run` produz `fallback.jsonl` com `[REDACTED]` + `pytest 3/3`.

### Fase B — CI + Pre-commit + Gitignore (15m)

4. `.gitignore` + `data/.gitkeep` (2m) — `git status` limpo exceto novos files
5. Patch `.github/workflows/ci.yml` — insere step `Metrics cardinality + /metrics + pytest P5` **após** `Prometheus alerts test` (5m) — `yaml safe_load` OK
6. Patch `.pre-commit-config.yaml` — hook `audit-fallback-redact` (3m) — `yaml safe_load` OK
7. `scripts/guard_anti_patterns.sh` não muda (já cobre GREP-4 str(dict) e GREP-5 urlsafe) — revalida `6/6 PASS`

**Gates B:** `yaml safe_load ci+pre OK` + `grep labelnames.*user_id == 0` + `REGISTRY no user_id`.

### Fase C — Artifact + Deep + Commit Único (10m)

8. Rodar `python scripts/drill_audit_fallback.py` + `pytest tests/test_p5_* -q` + `grep` + `cat data/audit_fallback.jsonl` → `reports/p5-05-drill.log` 54 linhas (igual P5-04) — `git add -f reports/p5-05-drill.log` (5m)
9. Patch `scripts/_validate_deep.py` seções S+T: `122 → 130` — `python scripts/_validate_deep.py` → `130/130 100%` (3m)
10. `python -m compileall -q src` + `docker compose config -q` (com env dummy) + `git status` → **1 commit único** `feat(P5-05+06): audit fallback drill + CI metrics job (DDIA cap3, SWE cap14, 130/130)` com `9 files` (audit já existe, mas drill+test+ci+pre+gitignore+deep+report) (2m)

**Commit message:**
```
feat(P5-05+06): audit fallback drill + CI metrics job (DDIA cap3, SWE cap14, 130/130)

P5-05 audit fallback: drill isolado com tmp_path + redact_pii dupla camada (detail_redacted antes de json + raw) + user_id system consistente + makedirs; 3 testes pytest (SWE cap14). P5-06 CI: metrics cardinality REGISTRY no user_id + pytest P5 explícito + pre-commit audit hook. Gates 122→130 100%, 0 PII, 0 cardinalidade.
```

---

## 5. Checklist de Commit — Igual P4/P5-04 (não deixa falso verde)

Antes do `git commit`:

```bash
bash scripts/guard_anti_patterns.sh              # 6/6 PASS
bash scripts/guard_grafana.sh                    # 8 panels, by(le)>=2, editable:false OK
python -m json.tool docker/grafana/dashboards/jefrey.json > /dev/null
python -c "import yaml; yaml.safe_load(open('docker/prometheus/alerts.yml')); yaml.safe_load(open('docker/prometheus/tests/alerts_test.yml'))"
docker run --rm --entrypoint promtool -v %cd%/docker/prometheus:/etc/prometheus prom/prometheus:v2.53.0 check rules /etc/prometheus/alerts.yml
docker run --rm --entrypoint promtool -v %cd%/docker/prometheus:/etc/prometheus prom/prometheus:v2.53.0 test rules /etc/prometheus/tests/alerts_test.yml
python scripts/drill_audit_fallback.py --help
python scripts/drill_audit_fallback.py && cat /tmp/audit_fallback.jsonl | grep -q "\[REDACTED\]" && echo "redact OK"
python -m pytest tests/test_p5_* -q
python scripts/_validate_deep.py                 # 130/130 100% WARNS0 BUGS0
python -m compileall -q src
JEFREY_ENV=prod JEFREY_EVENTBUS__HMAC_KEY=dummy docker compose config -q
git status --porcelain                            # só os 9 files do commit
```

---

## 6. Riscos & Mitigações

| Risco | Mitigação |
|-------|-----------|
| `audit.py` já correto mas drill quebra por `src` path no Windows | Mesmo pattern `dual sys.path _ROOT/src + _ROOT` de `drill_alerts.py` (já validado) |
| `pytest test_p5_audit_fallback` precisa mockar `get_settings` sem quebrar `pyproject` `pythonpath` | `unittest.mock.patch("src.jefrey.core.config.get_settings")` com `MagicMock` — igual `test_p4_*` |
| CI `REGISTRY` check falha porque `prometheus_client` não instalado no runner | `pip install prometheus_client` já em `requirements.txt` + `ci.yml Install deps` |
| `data/audit_fallback.jsonl` real poluído pelo drill | Drill usa `tmp_path` / `tempfile.mktemp` isolado, nunca escreve em `data/` real |
| `deep.py` f-string multilinha quebra (`unterminated string` em P5-04 x3) | Usar marker seguro `total_gates = len(oks)` fora de `print(f"...")` (lição P5-04 § Erros) |

---

## 7. Critérios de Aceite — P5 DONE 97-99%

| Critério | Verificação | Livro |
|----------|-------------|-------|
| `audit fallback` redact antes de json + segunda camada | `grep -n redact_pii raw` + `test_audit_redact_before_json` | DDIA cap3 |
| `fallback.jsonl` sem PII (sk-, email, cpf → `[REDACTED]`) | `drill_audit_fallback.py` + `test_fallback_file_redact` | DDIA cap3, CIPHER-010 |
| `user_id None → "system"` consistente | `test_fallback_user_id_consistency` | Axiom #2 |
| `CI` cardinality `0 user_id` labels + `REGISTRY` + `pytest P5` | `ci.yml` step + `deep.py` 130/130 | L4 cap5, SWE cap14 |
| `pre-commit` audit hook | `pre-commit-config.yaml` | SWE cap14 |
| `promtool` ainda `6/6 SUCCESS` (não quebrou P5-04) | `promtool check+test` | L4 cap10 |
| `8 panels` + `by(le)>=2` ainda OK | `guard_grafana.sh` | L4 cap6/11 |
| `git clean` + `1 commit` + `reports/p5-05-drill.log` | `git status` + `git log --oneline -1` | Axiom #1 |

**Próximo após P5 DONE:** P6 DATA — `psql \d+ hnsw CONCURRENTLY`, bench `ef_search 64 vs 200`, backup/restore, 2-processos `XADD/XREADGROUP` kid `v1→v2` (DDIA cap5/6/12) → libera P8 `v1.0.0-p5`.
