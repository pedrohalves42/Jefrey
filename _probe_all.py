import pathlib, re
def safe_read(p):
    try:
        return pathlib.Path(p).read_text(encoding="utf-8", errors="replace")
    except: return ""
# verify_p7 lines
for fname in ["scripts/verify_p7.py","scripts/verify_p4.py","scripts/verify_p5.py","scripts/verify_p6.py","scripts/verify_p3b.py"]:
    t=safe_read(fname)
    print(f"\n===== {fname} {len(t)} chars {len(t.splitlines())} lines =====")
    # find test counts / defs
    for i,l in enumerate(t.splitlines()[:80],1):
        print(f"{i:3d} {l}")
    print("--- grep ASSERT/CHECK ---")
    for pat in ["def test","def verify","CHECK","assert","n8n","trigger","webhook","MCP","mcp","RAG","memory","prometheus","grafana","metric"]:
        cnt=t.lower().count(pat.lower())
        if cnt: print(f"  {pat}: {cnt}")
    # last 40 lines
    print("--- TAIL ---")
    for l in t.splitlines()[-40:]:
        print(l)
    print("\n")

# also check src/jefrey/api/connections verbose tail
print("===== connections.py full tail =====")
print(safe_read("src/jefrey/api/connections.py"))

print("\n===== docker-compose.yml n8n exact =====")
dc=safe_read("docker-compose.yml")
start=dc.find("  n8n:")
print(dc[start:start+3500])

print("\n===== metrics.py full =====")
print(safe_read("src/jefrey/core/metrics.py"))

print("\n===== tests list =====")
import pathlib
for p in sorted(pathlib.Path("tests").glob("*.py")):
    t=safe_read(str(p))
    print(f"{p.name}: {len(t.splitlines())} lines")
    # first 20 lines
    for l in t.splitlines()[:20]:
        print(" ",l)
    print()
