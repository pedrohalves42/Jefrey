import pathlib, re, json, os
def safe(p): 
    try: return pathlib.Path(p).read_text(encoding="utf-8", errors="replace")
    except: return ""
# 1. verify_p7 checks extraction
t=safe("scripts/verify_p7.py")
print("VERIFY_P7 LINES", len(t.splitlines()))
# extract checks list
import re
m=re.search(r"checks\s*=\s*\[([^\]]+)\]", t, re.S)
if m: print(m.group(0)[:5000])
else:
    # else find lines with ("P07 or ("P0
    for i,l in enumerate(t.splitlines(),1):
        if '"P0' in l or "'P0" in l or "P07" in l:
            # print context 3 lines
            ctx=t.splitlines()[max(0,i-2):i+3]
            print(f"--- line {i} ---")
            for j,ll in enumerate(ctx, max(1,i-1)):
                print(j, ll)
            if i>350: break

print("\n=== MCP SERVER BLOCK in compose ===")
dc=safe("docker-compose.yml")
for marker in ["mcp-server","mcp","MCP"]:
    idx=dc.find(marker)
    if idx!=-1:
        print(dc[max(0,idx-200):idx+2000][:3000])
        break
# find mcp-server service exact
import re
mm=re.search(r"  mcp-server:.*?(?=\n  \w+:)", dc, re.S)
if mm: print("MCP SERVER SERVICE:\n", mm.group(0)[:3500])

print("\n=== DOCKERFILES ===")
for p in ["Dockerfile.api","Dockerfile.mcp","frontend/Dockerfile.frontend"]:
    print(p, pathlib.Path(p).exists(), pathlib.Path(p).stat().st_size if pathlib.Path(p).exists() else 0)
    if pathlib.Path(p).exists():
        print(safe(p)[:2500])

print("\n=== N8N WORKFLOW EXISTS ===")
for p in pathlib.Path(".").rglob("*.json"):
    if "n8n" in str(p).lower() or "workflow" in str(p).lower():
        print(p, p.stat().st_size)
        print(safe(str(p))[:3000])

print("\n=== FRONTEND SRC ===")
for p in sorted(pathlib.Path("frontend").rglob("*")):
    if p.is_file() and p.suffix in (".ts",".tsx",".json") and "node_modules" not in str(p):
        print(p, p.stat().st_size)
        if len(safe(str(p)))<10000:
            # just name
            pass
# list frontend/src
if pathlib.Path("frontend/src").exists():
    for p in sorted(pathlib.Path("frontend/src").rglob("*")):
        print("FE:", p)

print("\n=== verify_p7 checks IDs ===")
# parse check tuples roughly
for line in t.splitlines():
    if re.search(r'\(\s*"P0', line):
        print(line.strip()[:200])
# also try to run verify_p7 source checks offline via import
print("\n=== TRY RUN verify_p7 source checks dry ===")
import subprocess, sys
# run verify_p7 with python and capture first 200 lines
import subprocess
proc = subprocess.run([sys.executable, "scripts/verify_p7.py"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
print("STDOUT:", proc.stdout[:6000])
print("STDERR:", proc.stderr[:6000])
print("RC:", proc.returncode)

print("\n=== verify_p3b dry check file exists ===")
print("WF_PATH n8n/workflows/jefrey-event-router.json exists:", pathlib.Path("n8n/workflows/jefrey-event-router.json").exists())
if pathlib.Path("n8n/workflows").exists():
    for p in pathlib.Path("n8n/workflows").glob("*"):
        print(p, p.stat().st_size)

print("\n=== connections routes ===")
c=safe("src/jefrey/api/connections.py")
print(re.findall(r"@router\.(get|post|put|delete)\(\"([^\"]+)\"\)", c))
print("--- connections full head 3000 ---")
print(c[:3500])

print("\n=== mcp server src ===")
for p in sorted(pathlib.Path("src").rglob("*mcp*")):
    print(p, p.stat().st_size if p.is_file() else "-")
    if p.is_file():
        print(safe(str(p))[:2500])

print("\n=== metrics endpoint ===")
print(safe("src/jefrey/api/metrics_endpoint.py"))

print("\n=== prometheus config ===")
for p in ["docker/prometheus/prometheus.yml","docker/prometheus/alerts.yml","docker/grafana/dashboards/jefrey.json"]:
    print(p, pathlib.Path(p).exists(), pathlib.Path(p).stat().st_size if pathlib.Path(p).exists() else 0)
    if pathlib.Path(p).exists():
        print(safe(p)[:4000])
