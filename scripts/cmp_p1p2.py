import json, glob, sys, re

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

def _norm(s):
    # remove UUIDs e timestamps para comparar logica (nao ruido de uuid4 por run)
    return _UUID.sub("<UUID>", s)

def msgs(path):
    out = []
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
            out.append(_norm(o.get("message", "")))
        except Exception:
            out.append(_norm(line))
    return out

lines = []
ok = True
for base in ["p1", "p2"]:
    files = sorted(glob.glob(base + "_*.txt"))
    sets = [msgs(f) for f in files]
    same = all(s == sets[0] for s in sets[1:])
    succ = [any("verificado com sucesso" in m for m in s) for s in sets]
    lines.append("== %s runs=%d idempotente=%s sucesso_todos=%s linhas_run1=%d"
                 % (base, len(files), same, all(succ), len(sets[0])))
    if not same:
        ok = False
        import difflib
        for i in range(1, len(sets)):
            d = [l for l in difflib.unified_diff(sets[0], sets[i], "run1", "run%d" % i, lineterm="")
                 if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
            lines.append("   diff run1 vs run%d: %s" % (i, d[:10]))
    for m in sets[0]:
        if "verificado com sucesso" in m or "status=healthy" in m or "4 msgs" in m or "policy=enabled" in m:
            lines.append("   >> " + m)

with open("cmp_result.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
    fh.write("RESULT=%s\n" % ("IDEMPOTENTE" if ok else "NAO_IDEMPOTENTE"))
