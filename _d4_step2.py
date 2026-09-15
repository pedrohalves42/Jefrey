import pathlib, json, re, sys
def safe(p):
    try: return pathlib.Path(p).read_text(encoding="utf-8", errors="replace")
    except: return ""
print("=== verify_p3b run_core_checks ===")
t=safe("scripts/verify_p3b.py")
import re
m=re.search(r"def run_core_checks.*?(?=\n# )", t, re.S)
if m:
    print(m.group(0)[:9000])
else:
    print(t[3000:9000])
print("\n=== workflow httpRequest nodes ===")
wf=pathlib.Path("n8n/workflows/jefrey-event-router.json")
j=json.loads(safe(str(wf)))
for n in j["nodes"]:
    if n["type"]=="n8n-nodes-base.httpRequest":
        print(json.dumps(n, indent=2))
print("\n=== docs CONEXOES ===")
for p in sorted(pathlib.Path("docs").rglob("*")):
    if "conex" in str(p).lower() or "n8n" in str(p).lower():
        print(p, p.stat().st_size if p.is_file() else "dir")
        if p.is_file():
            print(safe(str(p))[:4000])
print("\n=== connections.py missing trigger endpoint ===")
c=safe("src/jefrey/api/connections.py")
print("routes:", re.findall(r'@router\.(post|get)\("([^"]+)"\)', c))
print("has /n8n/trigger?", "/n8n" in c)
print("has /trigger?", "trigger" in c.lower())
print("has X-User-Id?", "X-User-Id" in c)
print("has user_id?", "user_id" in c)
# what D4 expects per plan
print("\n=== D4 expected per TODO audit ===")
# read Todo notes
print(safe(".todo")[:2000] if pathlib.Path(".todo").exists() else "no .todo")
# read any D4 spec
for p in ["docs/cipher-audit/findings.md", "docs/cipher-audit/relatorio-cipher-jefrey.pdf"]:
    print(p, pathlib.Path(p).exists())
if pathlib.Path("docs/cipher-audit/findings.md").exists():
    print(safe("docs/cipher-audit/findings.md")[:5000])
print("\n=== mcp server _run_guarded snippet ===")
s=safe("src/jefrey/mcp/server.py")
# find guarded
for i,l in enumerate(s.splitlines(),1):
    if "_run_guarded" in l or "PolicyEngine" in l or "Approval" in l:
        print(f"{i:3d} {l}")
        if i>120: break
# show first 150 lines
print(s[:7000])
