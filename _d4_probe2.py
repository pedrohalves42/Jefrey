import pathlib, os, re, sys
print("=== api ===")
for p in sorted(pathlib.Path("src/jefrey/api").glob("*.py")):
    print(p.name, p.stat().st_size)
print("=== tests ===")
for p in sorted(pathlib.Path("tests").glob("*.py")):
    print(p.name, p.stat().st_size)
print("=== core ===")
for p in sorted(pathlib.Path("src/jefrey/core").glob("*.py")):
    print(p.name, p.stat().st_size)
print("=== rglob n8n ===")
for p in sorted(pathlib.Path(".").rglob("*n8n*")):
    s = p.stat().st_size if p.is_file() else -1
    print(p, "is_file", p.is_file(), "size", s)
    if p.is_file() and p.suffix in (".json",".yml",".yaml",".md") and s < 200000:
        try:
            print(pathlib.Path(p).read_text(encoding="utf-8", errors="replace")[:3000])
        except: pass
print("=== rglob workflow ===")
for p in sorted(pathlib.Path(".").rglob("*workflow*")):
    print(p, p.stat().st_size if p.is_file() else "-")
    if p.is_file() and p.suffix==".json":
        print(pathlib.Path(p).read_text(encoding="utf-8", errors="replace")[:3000])
print("=== connections full ===")
print(pathlib.Path("src/jefrey/api/connections.py").read_text(encoding="utf-8", errors="replace"))
print("=== docker-compose n8n block exact ===")
dc=pathlib.Path("docker-compose.yml").read_text(encoding="utf-8", errors="replace")
# extract n8n service verbatim
idx=dc.find("  n8n:")
print(dc[idx:idx+4000])
print("=== scripts ===")
for p in sorted(pathlib.Path("scripts").glob("*.py")):
    print(p, p.stat().st_size)
    print(pathlib.Path(p).read_text(encoding="utf-8", errors="replace")[:2000])
