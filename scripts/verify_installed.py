"""Verificacao automatica do Jefrey instalado (roda contra o servidor ja aberto).

Uso:  python scripts/verify_installed.py [http://localhost:8000]
Saida: uma linha OK/FALHOU por item; codigo de saida 0 so se tudo passou. Nunca mostra tokens nem chaves.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import httpx

SPA_PAGES = ("/", "/aprender", "/conexoes", "/skills", "/aprendi", "/estudos", "/configuracoes", "/ajuda", "/orb")
API_GET = ("health", "legal/status", "brains", "connections/google", "voice/cloud", "updates/check", "system/telemetry", "system/shell", "system/autostart", "alexa", "studies/sources")

Result = tuple[str, bool, str]


def _get(c: httpx.Client, path: str, **kw) -> httpx.Response:
    return c.get(path, **kw)


def run_checks(base_url: str, transport: Optional[httpx.BaseTransport] = None) -> list[Result]:
    out: list[Result] = []
    with httpx.Client(base_url=base_url, timeout=15, transport=transport) as c:
        try:
            tok = c.post("/auth/dev-token").json()["access_token"]
        except Exception as e:
            return [("login de teste", False, f"nao consegui o token ({type(e).__name__})")]
        auth = {"Authorization": f"Bearer {tok}"}
        for name in API_GET:
            try:
                r = _get(c, "/" + name, headers=auth if name != "health" else None)
                out.append((name.split("/")[0], r.status_code == 200, f"HTTP {r.status_code}"))
            except Exception as e:
                out.append((name.split("/")[0], False, type(e).__name__))
        try:
            skills = _get(c, "/skills", headers=auth).json().get("skills", [])
            riscos = {t.get("risk") for s in skills for t in s.get("tools", [])}
            bad = sorted(str(r) for r in riscos if r in (None, "unknown"))
            out.append(("skills sem risco desconhecido", not bad and bool(skills), "ok" if not bad else f"riscos: {bad}"))
        except Exception as e:
            out.append(("skills sem risco desconhecido", False, type(e).__name__))
        try:
            r = c.post("/wa/open-extension-folder", headers=auth)
            path = (r.json() or {}).get("path", "")
            out.append(("pasta da extensao", r.status_code == 200 and Path(path).is_dir(), "ok" if r.status_code == 200 else f"HTTP {r.status_code}"))
        except Exception as e:
            out.append(("pasta da extensao", False, type(e).__name__))
        for page in SPA_PAGES:
            try:
                r = _get(c, page, headers={"Accept": "text/html"})
                out.append((f"pagina {page}", r.status_code == 200 and "html" in r.headers.get("content-type", ""), f"HTTP {r.status_code}"))
            except Exception as e:
                out.append((f"pagina {page}", False, type(e).__name__))
    return out


def summarize(results: list[Result]) -> int:
    for name, ok, detail in results:
        print(f"{'OK    ' if ok else 'FALHOU'} {name}: {detail}")
    bad = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(bad)}/{len(results)} verificacoes passaram." + (f" Falharam: {', '.join(bad)}" if bad else ""))
    return 1 if bad else 0


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    return summarize(run_checks(base))


if __name__ == "__main__":
    sys.exit(main())
