import pathlib, os, re, json, textwrap, sys
def cat(p, n=120):
    fp=pathlib.Path(p)
    print(f"\n=== {p} exists={fp.exists()} ===")
    if not fp.exists(): return ""
    t=fp.read_text(encoding="utf-8", errors="replace")
    lines=t.splitlines()
    print(f"LINES {len(lines)}")
    for i,l in enumerate(lines[:n],1):
        print(f"{i:4d} | {l}")
    if len(lines)>n:
        print(f"... +{len(lines)-n} lines")
    return t

for p in ["docker-compose.yml","src/jefrey/api/connections.py","src/jefrey/core/mcp.py","src/jefrey/core/metrics.py","src/jefrey/api/main.py","src/jefrey/core/config.py"]:
    cat(p, 140)

# quick grep
import subprocess, pathlib
for p in ["src/jefrey/api/connections.py","src/jefrey/core/mcp.py","src/jefrey/core/metrics.py"]:
    fp=pathlib.Path(p)
    if fp.exists():
        t=fp.read_text(encoding="utf-8", errors="replace")
        for kw in ["n8n","webhook","trigger","MCP","mcp_calls","mcp_latency","user_id","HMAC","hmac","isolation"]:
            if kw.lower() in t.lower():
                print(f"[{p}] contains {kw}")

# check .env n8n
import pathlib
env=pathlib.Path(".env")
if env.exists():
    t=env.read_text(encoding="utf-8", errors="replace")
    for l in t.splitlines():
        if "N8N" in l or "n8n" in l.lower():
            print("ENV:",l)

# docker-compose n8n section
dc=pathlib.Path("docker-compose.yml").read_text(encoding="utf-8", errors="replace")
print("\n=== n8n in compose ===")
for i,l in enumerate(dc.splitlines(),1):
    if "n8n" in l.lower() or "5678" in l:
        # print context
        s=max(0,i-3); e=i+6
        print(f"--- around line {i} ---")
        for j in range(s,e):
            if 0 <= j < len(dc.splitlines()):
                print(f"{j+1:4d} | {dc.splitlines()[j]}")
