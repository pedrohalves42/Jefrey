import pathlib, re, json, sys, os
def safe(p):
    try: return pathlib.Path(p).read_text(encoding="utf-8", errors="replace")
    except Exception as e: return f"ERR {e}"
print("=== connections.py ===")
print(safe("src/jefrey/api/connections.py"))
print("\n=== main.py grep connections ===")
t=safe("src/jefrey/api/main.py")
for i,l in enumerate(t.splitlines(),1):
    if "connect" in l.lower() or "router" in l.lower():
        print(f"{i:3d} {l}")
print("\n=== metrics MCP ===")
t=safe("src/jefrey/core/metrics.py")
for i,l in enumerate(t.splitlines(),1):
    if "MCP" in l or "mcp" in l.lower():
        print(f"{i:3d} {l}")
        # context
        ctx=t.splitlines()[max(0,i-3):i+5]
        for j,ll in enumerate(ctx, max(1,i-2)):
            print(f"  {j:3d} {ll}")
print("\n=== mcp server health ===")
t=safe("src/jefrey/mcp/server.py")
for i,l in enumerate(t.splitlines(),1):
    if "health" in l.lower():
        print(f"{i:3d} {l}")
print("\n=== mcp server tools ===")
for i,l in enumerate(t.splitlines(),1):
    if "tool" in l.lower() and ("def " in l or "register" in l.lower() or "mcp.tool" in l.lower()):
        print(f"{i:3d} {l}")
print("\n=== mcp client ===")
t=safe("src/jefrey/mcp/client.py")
for i,l in enumerate(t.splitlines(),1):
    if "class" in l or "def " in l:
        print(f"{i:3d} {l}")
print("\n=== verify_p7 P07-042..045 checks ===")
t=safe("scripts/verify_p7.py")
for i,l in enumerate(t.splitlines(),1):
    if "P07-04" in l or "P07-03" in l:
        print(f"{i:3d} {l}")
        # next 5 lines
        for ll in t.splitlines()[i:i+6]:
            print(f"     {ll}")
print("\n=== docker-compose n8n ===")
dc=safe("docker-compose.yml")
start=dc.find("  n8n:")
print(dc[start:start+1800])
print("\n=== connections expected per P0-P7 plan ===")
# check what D4 should be: webhook real trigger
# search any existing trigger logic
print("connections.py has /n8n?", "/n8n" in safe("src/jefrey/api/connections.py"))
print("connections.py has trigger?", "trigger" in safe("src/jefrey/api/connections.py").lower())
# grep all api files for n8n
for p in sorted(pathlib.Path("src/jefrey/api").glob("*.py")):
    tt=safe(str(p))
    if "n8n" in tt.lower():
        print(f"{p.name} mentions n8n")
        for i,l in enumerate(tt.splitlines(),1):
            if "n8n" in l.lower():
                print(f"  {i:3d} {l}")
print("\n=== verify_p3b workflow path check ===")
# verify_p3b expects n8n/workflows/jefrey-event-router.json exists and webhook /jefrey-events
wf=pathlib.Path("n8n/workflows/jefrey-event-router.json")
print("wf exists", wf.exists(), "size", wf.stat().st_size if wf.exists() else 0)
if wf.exists():
    j=json.loads(safe(str(wf)))
    print("nodes", [n["name"] for n in j["nodes"]])
    # webhook node path
    for n in j["nodes"]:
        if n["type"]=="n8n-nodes-base.webhook":
            print("webhook params", n["parameters"])
