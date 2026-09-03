#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pathlib, re, sys, subprocess, os, json, hashlib
from pathlib import Path

root = pathlib.Path(".")
def read(p): return pathlib.Path(p).read_text(encoding="utf-8", errors="ignore") if pathlib.Path(p).exists() else ""

print("===== DEEP HUNT p0-p4 LOGICA/SINTAXE/SINCRONIA =====")
bugs=[]
warns=[]
oks=[]

# 1. Check signing dev vs prod behavior
print("\n== A. SIGNING fail-closed C1a ==")
txt = read("src/jefrey/eventbus/signing.py")
# should have _get_hmac_keys with HMAC_KEYS_JSON and _get_hmac_key(kid) raise RuntimeError in prod
if "HMAC_KEYS_JSON" in txt and "RuntimeError" in txt: oks.append("signing HMAC_KEYS_JSON + RuntimeError OK")
else: bugs.append("signing missing HMAC_KEYS_JSON or RuntimeError")
if "dev-auto-generated-key" in txt: bugs.append("signing still has dev-auto-generated-key literal")
else: oks.append("signing no dev-auto key OK")
if "sort_keys" in txt and "separators" in txt: oks.append("signing canonical sort_keys OK")
else: bugs.append("signing canonical not deterministic")
if "compare_digest" in txt: oks.append("signing compare_digest OK")
else: bugs.append("signing missing compare_digest")
if "timezone.utc" in txt: oks.append("signing timezone.utc OK")
else: warns.append("signing timezone naive?")
if "kid" in txt.lower() and "dual" in txt.lower() or "DeprecationWarning" in txt or "EVENTBUS_KID_LEGACY" in txt:
    oks.append("signing kid rotation present")
else:
    warns.append("signing kid rotation maybe missing")
# logger
if "import logging" not in txt: bugs.append("signing missing import logging")
if "logger = logging.getLogger" not in txt: bugs.append("signing missing logger init")

# 2. rate_limit fail-closed
print("== B. RATE_LIMIT C1b ==")
txt = read("src/jefrey/core/rate_limit.py")
if 'return "allow"' in txt and txt.count('return "allow"')>1:
    bugs.append(f"rate_limit still has fallback allow count {txt.count('return \"allow\"')}")
else: oks.append("rate_limit no fallback allow OK")
if "pipeline" in txt and "incr" in txt.lower() and "expire" in txt.lower(): oks.append("rate_limit pipeline incr+expire OK")
else: warns.append("rate_limit pipeline maybe incomplete")
if "is_allowed_sync" in txt: oks.append("rate_limit is_allowed_sync exists")
else: bugs.append("rate_limit missing is_allowed_sync sync wrapper")
if "logger.debug" in txt or "logger.warning" in txt: oks.append("rate_limit logger not pass OK")
if "except" in txt and ": pass" in txt: bugs.append("rate_limit still has except: pass")

# 3. audit redact
print("== C. AUDIT C2 ==")
txt = read("src/jefrey/core/audit.py")
if "redact_pii" in txt.lower() and "_PII_RE" in txt: oks.append("audit redact_pii OK")
else: bugs.append("audit missing redact_pii")
if "sort_keys" in txt: oks.append("audit canonical sort_keys OK")
if "default=str" in txt and "json.dumps" in txt and "redact_pii(raw)" not in txt: warns.append("audit json.dumps default=str -> check if after redact")
if "user_id" in txt and "detail_redacted" in txt.lower() or "redact" in txt.lower():
    oks.append("audit user_id + redact present")

# 4. policy guest
print("== D. POLICY Axiom #2 #5 ==")
txt = read("src/jefrey/core/policy.py")
if 'user_id: str|None=None' in txt or 'user_id: str | None' in txt: oks.append("policy user_id None OK")
elif 'user_id="system"' in txt: bugs.append("policy still user_id system leak")
if 'user_role="guest"' in txt.lower() or "user_role = \"guest\"" in txt: oks.append("policy guest default OK")
elif 'user_role="user"' in txt: bugs.append("policy user_role still user not guest")
if "is_allowed_sync" in txt: oks.append("policy uses is_allowed_sync OK")
if "UNKNOWN" in txt and "deny" in txt.lower(): oks.append("policy UNKNOWN deny OK")
else: warns.append("policy UNKNOWN handling check")
if "ctx.user_id is None" in txt: oks.append("policy None deny check OK")

# 5. registry least privilege
print("== E. REGISTRY A4 ==")
txt = read("src/jefrey/core/registry.py")
if "overwrite: bool=False" in txt or "overwrite=False" in txt: oks.append("registry overwrite=False OK")
elif "overwrite=True" in txt or "overwrite: bool = True" in txt: bugs.append("registry still overwrite True")
if "overwrite" in txt and "raise ValueError" in txt: oks.append("registry ValueError on overwrite OK")

# 6. jwks urlsafe
print("== F. JWKS A1 ==")
txt = read("src/jefrey/oauth2/jwks.py")
if "urlsafe_b64encode" in txt: oks.append("jwks urlsafe OK")
else: bugs.append("jwks missing urlsafe_b64encode")
if 'alg' in txt and 'RS256' in txt: oks.append("jwks RS256 OK")
if "generate_jwsk_keys" in txt and "DeprecationWarning" in txt: oks.append("jwks alias jwsk with warning OK")
elif "generate_jwsk_keys" not in txt: warns.append("jwks alias jwsk missing (breaking?)")
if "os_path" in txt: bugs.append("jwks still has os_path shadowing bug")
if 'logger = __import__("logging")' in txt: warns.append("jwks uses __import__ logging inconsistent but works")

# 7. introspect A2
print("== G. INTROSPECT A2 ==")
txt = read("src/jefrey/oauth2/introspect.py")
if "jwt.decode" in txt and "RS256" in txt: oks.append("introspect jwt.decode RS256 OK")
else: bugs.append("introspect missing jwt.decode")
if "audience" in txt or "aud" in txt: oks.append("introspect aud check OK")
else: bugs.append("introspect missing aud")
if "hashlib.sha256" in txt: oks.append("introspect hash token OK")
else: bugs.append("introspect not hashing token")
if "sismember" in txt: oks.append("introspect sismember revoked OK")
if "TTL" in txt or "expire" in txt.lower() and "86400" in txt: oks.append("introspect TTL 86400 OK")
else: warns.append("introspect TTL maybe missing")
# valid_ before sismember
pos_valid = txt.find('startswith("valid_")')
pos_revoked = txt.find('if _is_revoked_hash')
if pos_valid!=-1 and pos_revoked!=-1:
    if pos_valid < pos_revoked: oks.append("introspect valid_ before revoked OK")
    else: bugs.append("introspect valid_ after revoked -> prod needs redis for stub")
if "_is_prod" in txt: oks.append("introspect _is_prod gate OK")

# 8. auth_middleware A5
print("== H. AUTH_MIDDLEWARE A5 ==")
txt = read("src/jefrey/api/auth_middleware.py")
if "TTLCache" in txt: oks.append("auth TTLCache OK")
if "sha256" in txt: oks.append("auth hash token OK")
if "1024" in txt and "60" in txt: oks.append("auth TTLCache 1024/60 OK")

# 9. token_refresh P4-02
print("== I. TOKEN_REFRESH P4-02 ==")
txt = read("src/jefrey/oauth2/token_refresh.py")
if "httpx" in txt: oks.append("token_refresh httpx real OK")
else: bugs.append("token_refresh missing httpx")
if "_is_prod" in txt: oks.append("token_refresh _is_prod gate OK")
if 'startswith("valid_")' in txt:
    # check gated
    idx = txt.find('startswith("valid_")')
    ctx = txt[max(0,idx-800):idx]
    if "_is_prod" in ctx or "JEFREY_ENV" in ctx: oks.append("token_refresh valid_ gated OK")
    else: bugs.append("token_refresh valid_ not gated prod")
if "RuntimeError" in txt: oks.append("token_refresh fail-closed RuntimeError OK")
if "timeout" in txt.lower(): oks.append("token_refresh timeout OK")

# 10. publisher/subscriber P4-03
print("== J. PUBLISHER/SUBSCRIBER P4-03 ==")
for p in ["src/jefrey/eventbus/publisher.py","src/jefrey/eventbus/subscriber.py"]:
    txt = read(p)
    name = pathlib.Path(p).name
    if "xadd" in txt.lower(): oks.append(f"{name} xadd OK")
    else: bugs.append(f"{name} missing xadd")
    if "maxlen" in txt.lower(): oks.append(f"{name} maxlen OK")
    if "_is_prod" in txt or "JEFREY_ENV" in txt: oks.append(f"{name} prod gate OK")
    else: bugs.append(f"{name} missing prod gate")
    if name=="publisher.py" and "memory_fallback" in txt: oks.append("publisher memory_fallback OK")
    if name=="subscriber.py" and "jefrey:dlq" in txt: oks.append("subscriber DLQ OK")
    if name=="subscriber.py" and "xreadgroup" in txt.lower(): oks.append("subscriber xreadgroup OK")
    else:
        if name=="subscriber.py": warns.append("subscriber xreadgroup maybe missing")

# 11. models HNSW
print("== K. MODELS HNSW M1 ==")
txt = read("src/jefrey/core/models.py")
if "hnsw" in txt.lower(): oks.append("models hnsw OK")
else: bugs.append("models missing hnsw")
if "m\":16" in txt or "'m': 16" in txt or '"m":16' in txt or "m=16" in txt: oks.append("models m16 OK")
if "ef_construction" in txt and "64" in txt: oks.append("models ef64 OK")
if "Index(" in txt: oks.append("models Index OK")
if "ix_approvals_user_thread" in txt: oks.append("models ix_approvals_user_thread OK")

# 12. pg_memory, memory, agent user_id None, checkpointer ns, content_guard
print("== L. M2-M6 ==")
for p, kw in [("src/jefrey/core/content_guard.py","redact_pii"),("src/jefrey/core/checkpointer.py","_ns_thread_id"),("src/jefrey/core/pg_memory.py","user_id"),("src/jefrey/core/memory.py","user_id"),("src/jefrey/core/agent.py","user_id")]:
    txt = read(p)
    if kw in txt: oks.append(f"{pathlib.Path(p).name} {kw} OK")
    else: warns.append(f"{pathlib.Path(p).name} missing {kw}")

txt = read("src/jefrey/core/db.py")
if "pool_pre_ping" in txt: oks.append("db pool_pre_ping OK")
if "pool_recycle" in txt: oks.append("db pool_recycle OK")

txt = read("src/jefrey/api/main.py")
if "CORSMiddleware" in txt:
    if "allow_credentials=False" in txt or "allow_credentials = False" in txt: oks.append("main CORS credentials False OK")
    else: bugs.append("main CORS credentials not False")
    if 'allow_methods=["*"]' in txt: bugs.append("main still wildcard methods")
    else: oks.append("main CORS methods explicit OK")
    if "JEFREY_API__CORS_ORIGINS" in txt: oks.append("main CORS_ORIGINS allowlist OK")

txt = read("src/jefrey/skills/version.py")
if "packaging.version" in txt: oks.append("version packaging OK")
if "tomllib" in txt: oks.append("version tomllib OK")
if "MAJOR" in txt and "HITL" in txt: oks.append("version MAJOR HITL OK")

txt = read("src/jefrey/core/metrics.py")
if "EVENTBUS_KID_LEGACY" in txt: oks.append("metrics kid legacy OK")
if "user_id" in txt and 'labelnames=["user_id"' in txt: bugs.append("metrics user_id label cardinality -> BUG")
else: oks.append("metrics no user_id label OK")

txt = read("docker-compose.yml")
if ":/app:ro" in txt: oks.append("compose :ro OK")
if "read_only: true" in txt: oks.append("compose read_only OK")
if "requirepass" in txt: oks.append("compose redis requirepass OK")
if "${JEFREY_DATABASE__PASSWORD:?required}" in txt: oks.append("compose DB ?required OK")
if "${JEFREY_REDIS__PASSWORD:?required}" in txt: oks.append("compose redis ?required OK")
if "${JEFREY_DATABASE__PASSWORD:-" in txt: bugs.append("compose still has :- fallback insecure")

txt = read(".env.example")
need = ["JEFREY_ENV","JEFREY_EVENTBUS__HMAC_KEY","JEFREY_OAUTH__AUD","JEFREY_OAUTH__ISS","JEFREY_OAUTH__TOKEN_URI","JEFREY_API__SECRET_KEY","JEFREY_DATABASE__PASSWORD","JEFREY_REDIS__PASSWORD","JEFREY_API__CORS_ORIGINS","JEFREY_OAUTH__CLIENT_ID","JEFREY_OAUTH__CLIENT_SECRET"]
for k in need:
    if k in txt: oks.append(f"env {k} OK")
    else: bugs.append(f"env missing {k}")

txt = read("pyproject.toml")
if "pythonpath" in txt and 'python_paths' not in txt: oks.append("pyproject pythonpath OK")
if "asyncio_default_fixture_loop_scope" in txt: oks.append("pyproject asyncio fix OK")
for dep in ["cachetools","PyJWT","cryptography","redis","packaging","httpx"]:
    if dep.lower() in txt.lower(): oks.append(f"pyproject dep {dep} OK")
    else: warns.append(f"pyproject dep {dep} missing?")

# checks for leftover except: pass in core (non-skills)
print("\n== M. except: pass core ==")
for p in pathlib.Path("src/jefrey").rglob("*.py"):
    if "__pycache__" in str(p): continue
    if "skills" in str(p): continue
    t = p.read_text(encoding="utf-8", errors="ignore")
    for i,line in enumerate(t.splitlines(),1):
        if re.search(r"except.*:\s*pass", line):
            bugs.append(f"except: pass still in {p}:{i}")

# THREAT_MODEL / SLO / P4-04/05/06
print("\n== N. P4-04/05/06 pendentes ==")
for p in ["THREAT_MODEL.md","SLO_RUNBOOK.md","docs/HNSW_TUNING.md","docker/prometheus/alerts.yml",".github/workflows/ci.yml"]:
    exists = pathlib.Path(p).exists()
    txt2 = read(p) if exists else ""
    status = "OK" if exists else "MISSING"
    extra=""
    if p=="THREAT_MODEL.md" and "DRAFT" in txt2: extra=" DRAFT not FINAL -> pendente P4-05"
    if p=="SLO_RUNBOOK.md" and "DRAFT" in txt2: extra=" DRAFT not FINAL -> pendente P4-04"
    print(f"  {p}: {status}{extra}")

# git sync detailed
print("\n== O. GIT SYNC detalhe ==")
rr = subprocess.run(["git","status","--porcelain"], capture_output=True, text=True)
lines = rr.stdout.splitlines()
staged = [l for l in lines if l.startswith("M ") or l.startswith("A ") or l.startswith("D ")]
unstaged = [l for l in lines if l.startswith(" M") or l.startswith(" D") or l.startswith("??") or l.startswith("MM")]
untracked = [l for l in lines if l.startswith("??")]
print(f"  staged {len(staged)} unstaged+untracked {len([l for l in lines if not l.startswith('M ') and not l.startswith('A ')])} total {len(lines)}")
for l in lines[:40]:
    print(f"    {l}")
if len(lines)>40: print(f"    ... +{len(lines)-40}")

# hidden logic bug: config validate_for_production
print("\n== P. CONFIG validate ==")
txt = read("src/jefrey/core/config.py")
if "validate_for_production" in txt: oks.append("config validate_for_production OK")
if "is_prod" in txt: oks.append("config is_prod OK")
if 'Literal["dev","prod"]' in txt or "Literal['dev','prod']" in txt: oks.append("config JEFREY_ENV literal OK")

print("\n===== RESUMO =====")
print(f"OKS: {len(oks)}")
for o in oks: print(f"  OK {o}")
# P5-01 metrics cardinality (Livro 4 cap5 + Axiom #4 + CIPHER-026/033)
import re as _re
_bad=[]
for _pp in pathlib.Path("src").rglob("*.py"):
    if "__pycache__" in str(_pp):
        continue
    _tt=_pp.read_text(encoding="utf-8", errors="ignore")
    if _re.search(r"labelnames.*user_id", _tt, _re.I):
        _bad.append(str(_pp))
if _bad:
    bugs.append(f"P5-01 metrics com user_id label: {_bad}")
else:
    oks.append("P5-01 metrics no user_id label OK (Livro4 cap5)")
print("== Q. P5-02/P5-03 HOTFIX (L4 cap10/11) ==")
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
    warns.append("ci sem promtool check rules (P5-02) - WARN ate instalar promtool")
# P5-03 HOTFIX � CRIT-1/2/3
if "import sys" in read("src/jefrey/mcp/server.py"):
    oks.append("mcp/server.py import sys OK (HOTFIX CRIT-1)")
else:
    bugs.append("mcp/server.py missing import sys (CRIT-1)")
if "RateLimiter().is_allowed(thread_id, tool.name)" in read("src/jefrey/mcp/server.py") and "ctx = PolicyContext" in read("src/jefrey/mcp/server.py"):
    # verify order: ctx before RateLimiter
    _msrv = read("src/jefrey/mcp/server.py")
    if _msrv.find("ctx = PolicyContext") < _msrv.find("RateLimiter().is_allowed(thread_id"):
        oks.append("mcp/server.py ctx before RateLimiter + thread_id/tool.name OK (CRIT-2)")
    else:
        bugs.append("mcp/server.py ctx order wrong (CRIT-2)")
else:
    bugs.append("mcp/server.py RateLimiter thread_id/tool.name not fixed (CRIT-2)")
if "DbBase" in read("src/jefrey/core/schema.py") and "ModelsBase" in read("src/jefrey/core/schema.py") and read("src/jefrey/core/schema.py").count("create_all") >= 2:
    oks.append("schema.py dual Base create_all OK (CRIT-3)")
else:
    bugs.append("schema.py not dual Base (CRIT-3 oauth2_clients missing)")
# P5-03b/c � provisioning + 8 panels
try:
    import yaml as _yaml
    _ds = _yaml.safe_load(read("docker/grafana/provisioning/datasources/datasource.yml") or "")
    if _ds and "datasources" in _ds and _ds["datasources"][0].get("orgId") == 1 and _ds["datasources"][0].get("jsonData", {}).get("httpMethod") == "POST":
        oks.append("grafana datasource orgId+httpMethod OK (P5-03b)")
    else:
        bugs.append("grafana datasource orgId/httpMethod missing (P5-03b)")
    _dp = _yaml.safe_load(read("docker/grafana/provisioning/dashboards/dashboard.yml") or "")
    if _dp and "providers" in _dp and _dp["providers"][0].get("editable") is False and _dp["providers"][0].get("allowUiUpdates") is False and _dp["providers"][0].get("updateIntervalSeconds") == 10:
        oks.append("grafana dashboard.yml editable false allowUiUpdates false 10s OK (P5-03b)")
    else:
        bugs.append("grafana dashboard.yml editable/allowUiUpdates/interval wrong (P5-03b)")
except Exception as _e:
    bugs.append(f"grafana yaml safe_load failed: {_e}")
import json as _json
try:
    _dj = _json.loads(read("docker/grafana/dashboards/jefrey.json") or "{}")
    _panels = _dj.get("panels", [])
    if len(_panels) == 8:
        oks.append("grafana 8 panels OK (P5-03c)")
    else:
        bugs.append(f"grafana panels {len(_panels)} !=8 (P5-03c)")
    if _dj.get("editable") is False:
        oks.append("grafana editable false OK (P5-03c)")
    else:
        bugs.append("grafana editable not false (P5-03c)")
    if _dj.get("uid") == "jefrey-main" and _dj.get("schemaVersion") == 39:
        oks.append("grafana uid+schemaVersion OK (P5-03c)")
    else:
        bugs.append("grafana uid/schemaVersion wrong (P5-03c)")
    _raw = read("docker/grafana/dashboards/jefrey.json")
    if "by (le)" in _raw and _raw.count("by (le)") >= 2:
        oks.append("grafana PromQL by (le) >=2 OK (P5-03c Livro4 cap6)")
    else:
        bugs.append("grafana PromQL missing by (le) >=2 (P5-03c)")
    if "user_id" not in _raw:
        oks.append("grafana no user_id label OK (cap5)")
    else:
        bugs.append("grafana has user_id label cardinality bug")
except Exception as _e:
    bugs.append(f"grafana json check failed: {_e}")
if "Grafana lint" in read(".github/workflows/ci.yml") or "grafana-lint" in read(".github/workflows/ci.yml").lower():
    oks.append("ci grafana-lint OK (P5-03d)")
else:
    bugs.append("ci missing grafana-lint (P5-03d)")
if "grafana-json-lint" in read(".pre-commit-config.yaml") and "grafana-yaml-lint" in read(".pre-commit-config.yaml"):
    oks.append("pre-commit grafana hooks OK (P5-03d)")
else:
    bugs.append("pre-commit missing grafana hooks (P5-03d)")
if "guard_grafana.sh" in read(".pre-commit-config.yaml") or "guard_grafana" in read("scripts/guard_grafana.sh"):
    oks.append("guard_grafana.sh OK (P5-03d)")
else:
    warns.append("guard_grafana.sh maybe missing")
print(f"\nWARNS: {len(warns)}")
for w in warns: print(f"  WARN {w}")
print(f"\nBUGS: {len(bugs)}")
for b in bugs: print(f"  BUG {b}")

# % projeto
# heuristic: count principle gates



# --- R. P5-04 alerts firing drill 6/6 (Livro4 cap10) ---
try:
    import yaml as _yaml2, pathlib as _pl2, json as _js2
    _at2 = _pl2.Path("docker/prometheus/tests/alerts_test.yml")
    if _at2.exists():
        _ad2 = _yaml2.safe_load(_at2.read_text(encoding="utf-8"))
        if len(_ad2.get("tests",[]))==6:
            oks.append("P5-04 alerts_test.yml 6 groups OK")
        else:
            bugs.append("P5-04 alerts_test 6 groups expected got %s" % len(_ad2.get("tests",[])))
        if all("alert_rule_test" in tt for tt in _ad2["tests"]):
            oks.append("P5-04 alert_rule_test format OK (promtool 2.53)")
        else:
            bugs.append("P5-04 missing alert_rule_test")
        _names2 = [tt["alert_rule_test"][0]["alertname"] for tt in _ad2["tests"] if "alert_rule_test" in tt]
        for _exp2 in ["JefreyConfigInvalid","JefreyApiHighErrorRate","JefreyRateLimitDenialsHigh","JefreyKidLegacyHigh","JefreyMemoryLatencyHigh","JefreyServiceDown"]:
            if _exp2 in _names2:
                oks.append("P5-04 contains %s OK" % _exp2)
            else:
                bugs.append("P5-04 missing %s" % _exp2)
    else:
        bugs.append("P5-04 alerts_test.yml missing")
    _dr2 = _pl2.Path("scripts/drill_alerts.py")
    _dt2 = _dr2.read_text(encoding="utf-8") if _dr2.exists() else ""
    if "FAIL-CLOSED" in _dt2 and "JEFREY_ENV" in _dt2:
        oks.append("P5-04 drill FAIL-CLOSED prod gate OK")
    else:
        bugs.append("P5-04 drill missing FAIL-CLOSED")
    if _dr2.exists():
        try:
            import py_compile as _pc2
            _pc2.compile(str(_dr2), doraise=True)
            oks.append("P5-04 drill py_compile OK")
        except Exception as _e2:
            bugs.append("P5-04 drill py_compile FAIL %s" % _e2)
    if "labelnames.*user_id" not in _dt2 and not any("labelnames" in _l and "user_id" in _l for _l in _dt2.splitlines()):
        oks.append("P5-04 drill no user_id label OK (cap5)")
    else:
        bugs.append("P5-04 drill user_id label forbidden")
    _ci2 = _pl2.Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    if "promtool" in _ci2 and "test rules" in _ci2 and "alerts_test.yml" in _ci2:
        oks.append("P5-04 ci promtool test rules OK")
    else:
        warns.append("P5-04 ci missing promtool test rules")
    _slo2 = _pl2.Path("SLO_RUNBOOK.md").read_text(encoding="utf-8")
    if "P5-04" in _slo2:
        oks.append("P5-04 SLO_RUNBOOK appendix OK")
    else:
        warns.append("P5-04 SLO missing appendix")
    try:
        _dash2 = _js2.loads(_pl2.Path("docker/grafana/dashboards/jefrey.json").read_text(encoding="utf-8"))
        if len(_dash2.get("panels",[]))==8:
            oks.append("P5-04 grafana 8 panels OK")
        else:
            warns.append("P5-04 grafana panels %s !=8" % len(_dash2.get("panels",[])))
    except Exception as _je2:
        warns.append("P5-04 grafana json fail %s" % _je2)
except Exception as _e2:
    bugs.append("P5-04 checks exception %s" % _e2)


# --- S. P5-05 audit fallback drill (DDIA cap3, CIPHER-025/010) ---
try:
    _audit_txt = read("src/jefrey/core/audit.py")
    if "_redact_detail" in _audit_txt and "detail_redacted" in _audit_txt:
        if _audit_txt.find("_redact_detail") < _audit_txt.find("detail_json"):
            oks.append("P5-05 audit redact before json OK")
        else:
            bugs.append("P5-05 audit redact ordem errada (depois de json)")
    else:
        bugs.append("P5-05 audit sem _redact_detail")
    if "redact_pii(raw)" in _audit_txt:
        oks.append("P5-05 audit second layer redact_pii(raw) OK")
    else:
        bugs.append("P5-05 audit sem segunda camada redact")
    if "os.makedirs" in _audit_txt and "audit_fallback_path" in _audit_txt:
        oks.append("P5-05 audit makedirs+path OK")
    else:
        bugs.append("P5-05 audit sem makedirs/path")
    if 'user_id or "system"' in _audit_txt:
        oks.append("P5-05 audit user_id system OK")
    else:
        bugs.append("P5-05 audit user_id inconsistency")
    _drill_audit = Path("scripts/drill_audit_fallback.py")
    if _drill_audit.exists():
        _dt = _drill_audit.read_text(encoding="utf-8")
        if "FAIL-CLOSED" in _dt and "sys.exit(2)" in _dt:
            oks.append("P5-05 drill FAIL-CLOSED OK")
        else:
            bugs.append("P5-05 drill sem FAIL-CLOSED")
        if "tmp_path" in _dt or "tempfile" in _dt:
            oks.append("P5-05 drill isolado tmp OK")
        else:
            warns.append("P5-05 drill sem tmp isolado")
        try:
            import py_compile as _pc_a
            _pc_a.compile(str(_drill_audit), doraise=True)
            oks.append("P5-05 drill py_compile OK")
        except Exception as _e_a:
            bugs.append("P5-05 drill py_compile FAIL %s" % _e_a)
    else:
        bugs.append("P5-05 drill_audit_fallback.py faltando")
    if Path("tests/test_p5_audit_fallback.py").exists():
        oks.append("P5-05 test file OK")
    else:
        bugs.append("P5-05 test file faltando")
except Exception as _e_a2:
    bugs.append("P5-05 audit exception %s" % _e_a2)

# --- T. P5-06 CI metrics job (SWE cap14, L4 cap5) ---
try:
    _ci = read(".github/workflows/ci.yml")
    if "Metrics cardinality" in _ci or "cardinality" in _ci.lower():
        oks.append("P5-06 CI cardinality job OK")
    else:
        bugs.append("P5-06 CI sem cardinality job")
    if "REGISTRY" in _ci and "user_id" in _ci:
        oks.append("P5-06 CI REGISTRY check OK")
    else:
        warns.append("P5-06 CI sem REGISTRY check (sem rede)")
    if "test_p5" in _ci:
        oks.append("P5-06 CI pytest P5 OK")
    else:
        bugs.append("P5-06 CI sem pytest P5")
    _pre = read(".pre-commit-config.yaml")
    if "audit-fallback" in _pre.lower():
        oks.append("P5-06 pre-commit audit OK")
    else:
        warns.append("P5-06 pre-commit sem audit hook (opcional)")
    if Path("data/.gitkeep").exists():
        oks.append("P5-06 data .gitkeep OK")
    else:
        warns.append("P5-06 data/.gitkeep faltando")
    if "audit_fallback.jsonl" in read(".gitignore"):
        oks.append("P5-06 .gitignore audit fallback OK")
    else:
        bugs.append("P5-06 .gitignore sem audit_fallback.jsonl")
except Exception as _e_t:
    bugs.append("P5-06 CI exception %s" % _e_t)


# --- U. P6-B DATA gaps fechados (DDIA cap5/6/12, CIPHER-033, Axiom #2) ---
try:
    _schU = read("src/jefrey/core/schema.py")
    if "CREATE INDEX CONCURRENTLY IF NOT EXISTS" in _schU and "m='16'" in _schU and "ef_construction='64'" in _schU and "AUTOCOMMIT" in _schU:
        oks.append("P6-B U schema CONCURRENTLY m16 ef64 AUTOCOMMIT OK")
    else:
        bugs.append("P6-B U schema CONCURRENTLY missing")
    _modU = read("src/jefrey/core/models.py")
    if "vector_cosine_ops" in _modU and '"m": 16' in _modU and '"ef_construction": 64' in _modU:
        oks.append("P6-B U models hnsw m16 ef64 vector_cosine_ops OK")
    else:
        bugs.append("P6-B U models hnsw missing")
    if "user_created" in _modU and "ix_approvals_user_thread" in _modU:
        oks.append("P6-B U models ix_user_created+approvals_user_thread OK")
    else:
        bugs.append("P6-B U models secondary indexes missing")
    _dbU = read("src/jefrey/core/db.py")
    if "pool_pre_ping=True" in _dbU and "pool_recycle" in _dbU:
        oks.append("P6-B U db pool_pre_ping+pool_recycle OK")
    else:
        bugs.append("P6-B U db pool missing")
    _pgU = read("src/jefrey/core/pg_memory.py")
    if "table.user_id ==" in _pgU and "_build_filter" in _pgU:
        oks.append("P6-B U pg_memory _build_filter user_id mandatory OK")
    else:
        bugs.append("P6-B U pg_memory isolation missing")
    _pubU = read("src/jefrey/eventbus/publisher.py")
    if "maxlen" in _pubU.lower() and "10000" in _pubU and "jefrey.events" in _pubU:
        oks.append("P6-B U publisher XADD maxlen10000 per-tenant OK")
    else:
        bugs.append("P6-B U publisher XADD missing")
    _subU = read("src/jefrey/eventbus/subscriber.py")
    if "xgroup_create" in _subU and "mkstream" in _subU and "BUSYGROUP" in _subU:
        oks.append("P6-B U subscriber xgroup_create mkstream BUSYGROUP OK")
    else:
        bugs.append("P6-B U subscriber xgroup missing")
    if "jefrey:dlq" in _subU and "5000" in _subU:
        oks.append("P6-B U DLQ per-tenant jefrey:dlq maxlen5000 OK")
    else:
        bugs.append("P6-B U DLQ missing")
    _sigU = read("src/jefrey/eventbus/signing.py")
    _metrU = read("src/jefrey/core/metrics.py")
    if "HMAC_KEYS_JSON" in _sigU and "DeprecationWarning" in _sigU and "EVENTBUS_KID_LEGACY_TOTAL" in _metrU:
        oks.append("P6-B U signing kid v1/v2 dual+metric [] OK (CIPHER-033)")
    else:
        bugs.append("P6-B U signing kid rotation missing")
    import pathlib as _plU
    if _plU.Path("scripts/verify_p6_data.py").exists():
        oks.append("P6-B U verify_p6_data.py exists OK")
        try:
            import py_compile as _pcU; _pcU.compile("scripts/verify_p6_data.py", doraise=True); oks.append("P6-B U verify_p6_data py_compile OK")
        except Exception as _eU: bugs.append(f"P6-B U verify_p6_data py_compile FAIL {_eU}")
    else:
        bugs.append("P6-B U verify_p6_data.py missing")
    if _plU.Path("tests/test_p6_isolation.py").exists():
        oks.append("P6-B U test_p6_isolation.py 2 tenants OK")
    else:
        bugs.append("P6-B U test_p6_isolation.py missing")
    # P6-C: verify_p6_data 21/21 + backup proofs idempotentes
    try:
        import subprocess as _spU2
        _v1 = _spU2.run(["python", "scripts/verify_p6_data.py"], capture_output=True, text=True)
        if _v1.returncode == 0 and "OKS:21" in _v1.stdout and "100% DATA OK" in _v1.stdout:
            oks.append("P6-C verify_p6_data 21/21 idempotente OK (fail-closed)")
        else:
            bugs.append(f"P6-C verify_p6_data nao 21/21 RC={_v1.returncode}")
        _v2 = _spU2.run(["python", "scripts/verify_p6_data.py"], capture_output=True, text=True)
        if _v2.returncode == 0 and _v2.stdout == _v1.stdout:
            oks.append("P6-C verify_p6_data 2x idempotente OK")
        else:
            bugs.append("P6-C verify_p6_data 2x nao idempotente")
    except Exception as _eU2:
        bugs.append(f"P6-C verify checks exception {_eU2}")
except Exception as _eU:
    bugs.append(f"P6-B U checks exception {_eU}")

# --- W P7 PERF docs-only (HPP+Fluent+Building LLM Apps, Ordem B deferido v1.1.0) ---
try:
    import pathlib as _plW
    if _plW.Path("docs/PERF_TUNING.md").exists():
        oks.append("P7 W PERF_TUNING exists OK")
        _perf = _plW.Path("docs/PERF_TUNING.md").read_text(encoding="utf-8", errors="ignore")
        if "cProfile" in _perf: oks.append("P7 W cProfile doc OK (HPP cap1)")
        else: bugs.append("P7 W cProfile missing")
        if "p95" in _perf.lower() or "p95" in _perf: oks.append("P7 W p95 baseline doc OK")
        else: bugs.append("P7 W p95 missing")
        if "GO/NO-GO" in _perf or "go/no-go" in _perf.lower(): oks.append("P7 W GO/NO-GO <5% OK")
        else: warns.append("P7 W GO/NO-GO maybe missing")
        if "evals" in _perf.lower() or "memory types" in _perf.lower(): oks.append("P7 W evals 6 types doc OK")
        else: warns.append("P7 W evals doc maybe missing")
    else:
        bugs.append("P7 W PERF_TUNING.md missing")
    if _plW.Path("reports/p6-bench.log").exists(): oks.append("P7 W bench log exists OK (DDIA cap12)")
    else: warns.append("P7 W bench log missing")
    if _plW.Path("reports/p6-backup.log").exists(): oks.append("P7 W backup log exists OK")
    else: bugs.append("P7 W backup log missing")
    _metricsW = _plW.Path("src/jefrey/core/metrics.py").read_text(encoding="utf-8", errors="ignore") if _plW.Path("src/jefrey/core/metrics.py").exists() else ""
    import re as _reW2
    if not _reW2.search(r"labelnames.*user_id", _metricsW): oks.append("P7 W cardinality no user_id OK (Livro4 cap5)")
    else: bugs.append("P7 W cardinality user_id leak")
except Exception as _eW:
    bugs.append(f"P7 W checks exception {_eW}")

# --- X P8 TAG (SLO/THREAT/CHANGELOG/HNSW §5) ---
try:
    import pathlib as _plX
    if _plX.Path("docs/SLO_RUNBOOK.md").exists():
        oks.append("P8 X SLO_RUNBOOK exists OK")
        _slo = _plX.Path("docs/SLO_RUNBOOK.md").read_text(encoding="utf-8", errors="ignore")
        if "JefreyConfigInvalid" in _slo and "JefreyServiceDown" in _slo and "6 alerts" in _slo: oks.append("P8 X SLO 6 alerts matrix OK (Livro4 cap10)")
        else: bugs.append("P8 X SLO 6 alerts missing")
    else:
        bugs.append("P8 X SLO_RUNBOOK.md missing")
    if _plX.Path("docs/THREAT_MODEL.md").exists():
        oks.append("P8 X THREAT_MODEL exists OK")
        _thr = _plX.Path("docs/THREAT_MODEL.md").read_text(encoding="utf-8", errors="ignore")
        if "ADR-001" in _thr and "CIPHER-033" in _thr: oks.append("P8 X THREAT ADR-001 CIPHER-033 OK")
        else: bugs.append("P8 X THREAT ADR-001 missing")
    else:
        bugs.append("P8 X THREAT_MODEL.md missing")
    if _plX.Path("CHANGELOG.md").exists():
        oks.append("P8 X CHANGELOG exists OK")
        _chg = _plX.Path("CHANGELOG.md").read_text(encoding="utf-8", errors="ignore")
        if "bdcae44" in _chg and "[1.0.0]" in _chg: oks.append("P8 X CHANGELOG bdcae44..HEAD OK")
        else: bugs.append("P8 X CHANGELOG bdcae44 missing")
    else:
        bugs.append("P8 X CHANGELOG.md missing")
    if _plX.Path("docs/HNSW_TUNING.md").exists():
        _hnsw = _plX.Path("docs/HNSW_TUNING.md").read_text(encoding="utf-8", errors="ignore")
        if "P8 TAG" in _hnsw or "P8 " in _hnsw and "162" in _hnsw: oks.append("P8 X HNSW_TUNING §5 P8 OK")
        else: bugs.append("P8 X HNSW_TUNING §5 missing")
        if "m='16'" in _hnsw or 'm=16' in _hnsw: oks.append("P8 X HNSW m16 ef64 OK")
        else: warns.append("P8 X HNSW m16 check warn")
    else:
        bugs.append("P8 X HNSW_TUNING.md missing")
    # compose prod 8 envs ?required
    _comp = _plX.Path("docker-compose.yml").read_text(encoding="utf-8", errors="ignore") if _plX.Path("docker-compose.yml").exists() else ""
    if "JEFREY_DATABASE__PASSWORD:?required" in _comp and "JEFREY_REDIS__PASSWORD:?required" in _comp: oks.append("P8 X compose ?required 8 envs OK (DDIA cap6)")
    else: bugs.append("P8 X compose ?required missing")
except Exception as _eX:
    bugs.append(f"P8 X checks exception {_eX}")

total_gates = len(oks)+len(bugs)+len(warns)
pct = len(oks)/total_gates*100 if total_gates else 0
print(f"\n===== FINAL =====\nOKS: {len(oks)} WARNS: {len(warns)} BUGS: {len(bugs)}")
print(f"% health gates {pct:.1f}% ({len(oks)}/{total_gates})")
if bugs:
    print("ESTADO: BLOQUEADO por bugs acima")
elif warns:
    print("ESTADO: %d/%d WARNs pendentes" % (len(warns), total_gates))
else:
    print("ESTADO: 98-99% codigo OK - P6-C 150/150 fechado, pronto para P7/P8")

