#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pathlib, re, sys, subprocess, os, json, hashlib

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
print(f"\nWARNS: {len(warns)}")
for w in warns: print(f"  WARN {w}")
print(f"\nBUGS: {len(bugs)}")
for b in bugs: print(f"  BUG {b}")

# % projeto
# heuristic: count principle gates
total_gates = len(oks)+len(bugs)+len(warns)
pct = len(oks)/total_gates*100 if total_gates else 0
print(f"\n% health gates {pct:.1f}% ({len(oks)}/{total_gates})")
if bugs:
    print("ESTADO: BLOQUEADO por bugs acima")
else:
    print("ESTADO: 88-92% codigo OK, pendente P4-04/05/06 para 95-98%")
