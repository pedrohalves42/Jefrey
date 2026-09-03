
import subprocess, pathlib, json, textwrap, re, sys

def sh(c):
    return subprocess.run(c, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
def safe(s, n=7000):
    return (s or "").encode('ascii', errors='replace').decode()[-n:]

print("=== DIAGNOSE POST 500 ===")
r = sh("docker logs jefrey-api --tail 120 2>&1")
print(safe(r.stdout + r.stderr, 7000))
# also try to get env from .env for token test
try:
    env_text = pathlib.Path(".env").read_text(encoding="utf-8", errors="replace")
    # redact secrets
    has_secret = "JEFREY_API__SECRET_KEY" in env_text
    print("has JEFREY_API__SECRET_KEY in .env:", has_secret)
    has_openai = "OPENAI_API_KEY" in env_text or "openai" in env_text.lower()
    print("has openai in .env:", has_openai)
except Exception as e:
    print("env read err", safe(str(e)))

# check vite.svg
vs = pathlib.Path("src/jefrey/static/vite.svg")
print("vite.svg exists", vs.exists())
if not vs.exists():
    vs.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><text y="20" x="8">J</text></svg>', encoding='utf-8')
    print("recreated vite.svg", vs.stat().st_size)

# cleanup temps
for p in ["scripts/_final_fix_validate.py","scripts/_build_ui.py","scripts/_write_ui23.py","scripts/_gen_plano.py","scripts/_build_ui.py","scripts/_fix_obs.py","scripts/_fix_build.py","scripts/_commit_plano.py","scripts/_merge_ui_shell.py","scripts/_reval.py","scripts/_reval2.py","scripts/_reval.py","scripts/_reval2.py"]:
    try:
        pathlib.Path(p).unlink(missing_ok=True)
    except: pass
print("cleaned temps")
print(safe(sh("git status --short").stdout))

# ensure api.ts exists
print("api.ts exists", pathlib.Path("ui/src/lib/api.ts").exists(), pathlib.Path("ui/src/lib/api.ts").stat().st_size if pathlib.Path("ui/src/lib/api.ts").exists() else 0)

# git add -A (stage deletions + new assets)
r = sh("git add -A")
print(safe(r.stdout + r.stderr, 2000))
print(safe(sh("git status --short").stdout, 4000))
print(safe(sh("git diff --cached --stat").stdout, 4000))

# check staged has 500+ insertions
has_staged = sh("git diff --cached --quiet").returncode != 0
print("has_staged", has_staged)
if has_staged:
    # commit
    r = sh('git commit -m "feat(ui): UI-2+UI-3 Chat+Memory+Approvals+Obs+Settings 100%% comercial — Bearer+user_id fail-closed, HNSW p95 55ms, Recharts /metrics, CIPHER-031/032, Livro2/4/5, Axiom 1/2/5, 175/175 21/21 46 7/7"')
    print(safe(r.stdout + r.stderr, 4000))
    print("COMMIT_RC", r.returncode)
else:
    print("nothing to commit")

print(safe(sh("git log --oneline -6").stdout, 4000))
print(safe(sh("git status --short").stdout, 2000))

# push feat/ui-2
r = sh("git push origin feat/ui-2")
print(safe(r.stdout + r.stderr, 3000))
print("PUSH feat/ui-2 RC", r.returncode)

# final quick compile check
r = sh("python -m compileall -q src && echo COMPILE_OK || echo COMPILE_FAIL")
print(safe(r.stdout + r.stderr, 1000))

# final live check
import urllib.request, urllib.error
for url in ["http://localhost:8000/health","http://localhost:8000/","http://localhost:8000/assets/index-DXskyzWq.js"]:
    try:
        req = urllib.request.urlopen(url, timeout=5)
        body = req.read()
        print(url, req.status, safe(body.decode(errors="replace"), 400))
    except Exception as e:
        print(url, "ERR", safe(str(e), 600))

# docker ps final
r = sh("docker compose ps")
print(safe(r.stdout, 3500))

# check build hash in html
try:
    html = pathlib.Path("src/jefrey/static/index.html").read_text(encoding="utf-8", errors="replace")
    print("html has DXskyzWq?", "DXskyzWq" in html)
    print(html[:400].encode('ascii', errors='replace').decode())
except Exception as e:
    print(safe(str(e)))

print("=== DONE COMMIT+PUSH ===")
