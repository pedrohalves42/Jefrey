import pathlib, json, re, os, sys, subprocess

def safe(p):
    try: return pathlib.Path(p).read_text(encoding="utf-8", errors="replace")
    except: return ""

# 1. MCP package
print("=== MCP PACKAGE ===")
for p in sorted(pathlib.Path("src/jefrey").rglob("*")):
    if "mcp" in str(p).lower():
        print(p, "file" if p.is_file() else "dir", p.stat().st_size if p.is_file() else "-")
        if p.is_file() and p.stat().st_size<30000:
            print(safe(str(p))[:3500])
            print("---END",p,"---")

# 2. n8n workflow full
wf = pathlib.Path("n8n/workflows/jefrey-event-router.json")
print("\n=== WORKFLOW JSON ===")
if wf.exists():
    j=json.loads(safe(str(wf)))
    print("name:", j.get("name"), "nodes:", len(j.get("nodes",[])))
    for n in j.get("nodes",[]):
        print(" node:", n.get("name"), n.get("type"), n.get("typeVersion"))
        if "webhook" in n.get("type",""):
            print("  webhook params:", n.get("parameters"))
        if n.get("name")=="Build MCP Payload":
            print("  jsCode:", n.get("parameters",{}).get("jsCode","")[:800])
        if n.get("type")=="n8n-nodes-base.httpRequest":
            print("  httpRequest:", n.get("parameters"))
    # connections
    if "connections" in j:
        print(" connections keys:", list(j["connections"].keys())[:10])
        print(json.dumps(j["connections"], indent=2)[:4000])

# 3. prometheus + grafana
print("\n=== PROMETHEUS YML ===")
print(safe("docker/prometheus/prometheus.yml"))
print("\n=== ALERTS YML ===")
print(safe("docker/prometheus/alerts.yml"))
print("\n=== GRAFANA DASHBOARD ===")
gd=safe("docker/grafana/dashboards/jefrey.json")
if gd:
    try:
        j=json.loads(gd)
        print(" panels:", len(j.get("panels",[])), " title:", j.get("title"))
        for p in j.get("panels",[])[:10]:
            print("  panel:", p.get("title"), p.get("type"), str(p.get("targets",""))[:200])
    except: print(gd[:4000])
else:
    print(" NO dashboard file")

print("\n=== GRAFANA PROVISIONING ===")
for p in sorted(pathlib.Path("docker/grafana").rglob("*")):
    print(p, p.stat().st_size if p.is_file() else "dir")
    if p.is_file() and p.suffix in (".yml",".yaml",".json"):
        print(safe(str(p))[:2000])

# 4. verify_p7 full count
t=safe("scripts/verify_p7.py")
ids=re.findall(r'"(P07-\d+)"', t)
print("\n=== VERIFY_P7 IDS ===", len(ids), ids[:20], "...", ids[-20:])
# run verify_p7 and capture without json logger noise -> filter lines with P07
proc=subprocess.run([sys.executable,"scripts/verify_p7.py"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
out=proc.stdout+proc.stderr
# extract summary
for l in out.splitlines():
    if "P07-" in l or "SUMMARY" in l or "Total:" in l or "PASSED" in l or "FAIL" in l:
        print(l)
print("RC", proc.returncode)
# also show last 40 lines filtered
lines=[l for l in out.splitlines() if l.strip()]
print("\n--- last 80 raw lines ---")
for l in lines[-80:]:
    print(l[:500])

# 5. scripts verify counts
for fname in ["scripts/verify_p1.py","scripts/verify_p2.py","scripts/verify_p3a.py","scripts/verify_p3b.py","scripts/verify_p4.py","scripts/verify_p5.py","scripts/verify_p6.py"]:
    tt=safe(fname)
    cnts=re.findall(r'check\(|_check\(|@check', tt)
    print(fname, "checks approx", len(cnts), "lines", len(tt.splitlines()))

# 6. tests list details
print("\n=== TESTS ===")
for p in sorted(pathlib.Path("tests").glob("*.py")):
    tt=safe(str(p))
    print(p.name, len(tt.splitlines()), "defs:", len(re.findall(r"def test_", tt)))

# 7. frontend
print("\n=== FRONTEND ===")
for p in sorted(pathlib.Path("frontend").rglob("*")):
    if p.is_file() and "node_modules" not in str(p):
        print(p, p.stat().st_size)
        if p.suffix in (".json",".ts",".tsx",".js") and p.stat().st_size<8000:
            print(safe(str(p))[:1500])
            print("---")

# 8. connections routes expected vs actual
c=safe("src/jefrey/api/connections.py")
print("\n=== CONNECTIONS ROUTES ===")
print(re.findall(r'@router\.(post|get|put|delete)\("([^"]+)"\)', c))
print("has n8n trigger?", "trigger" in c.lower(), "webhook" in c.lower(), "X-User-Id" in c, "user_id" in c)

# 9. metrics cardinality
m=safe("src/jefrey/core/metrics.py")
lbs=re.findall(r'labelnames\s*=\s*\(([^)]*)\)', m)
print("\n=== METRICS labelnames ===")
for b in lbs:
    print(repr(b), "has user_id?", "user_id" in b)

# 10. compose services
dc=safe("docker-compose.yml")
print("\n=== COMPOSE SERVICES ===")
print(re.findall(r"^\s{2}(\w[\w-]+):", dc, re.M))

# 11. check .env n8n webhook url
env=safe(".env")
for l in env.splitlines():
    if "N8N" in l or "WEBHOOK" in l:
        print("ENV", l)
