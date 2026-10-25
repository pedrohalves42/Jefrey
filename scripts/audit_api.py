"""Varre TODAS as rotas GET (sem parametro de caminho) do Jefrey aberto e diz quais respondem, quais falham e quais pedem algo.

Uso:  python scripts/audit_api.py [http://127.0.0.1:8000] [usuario]
So le (GET); nunca muda nada. Rotas que gastam IA ou sao lentas por natureza ficam de fora (lista SKIP).
"""
from __future__ import annotations

import sys
import time

import httpx

SKIP = {"/chat/stream", "/brains/check", "/metrics", "/docs", "/redoc", "/openapi.json", "/auth/google/login", "/auth/dev-token", "/voice/speak", "/system/quit"}


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    user = sys.argv[2] if len(sys.argv) > 2 else "demo"
    with httpx.Client(base_url=base, timeout=40) as c:
        tok = c.post("/auth/dev-token", json={"user_id": user}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        spec = c.get("/openapi.json").json()
        rows = []
        for path, ops in sorted(spec["paths"].items()):
            if "get" not in ops or "{" in path or path in SKIP:
                continue
            t0 = time.perf_counter()
            try:
                r = c.get(path, headers=h)
                code, size = r.status_code, len(r.content)
            except Exception as e:
                code, size = type(e).__name__, 0
            rows.append((path, code, time.perf_counter() - t0, size))
    ok = [r for r in rows if isinstance(r[1], int) and r[1] < 300]
    bad = [r for r in rows if r not in ok]
    slow = sorted((r for r in ok if r[2] > 2.0), key=lambda r: -r[2])
    print(f"{len(rows)} rotas GET testadas: {len(ok)} respondem, {len(bad)} com problema, {len(slow)} lentas (> 2 s)\n")
    for p, code, dt, size in bad:
        print(f"PROBLEMA {code}  {p}  ({dt:.1f}s)")
    for p, code, dt, size in slow:
        print(f"LENTA    {dt:5.1f}s  {p}")
    return 1 if any(isinstance(r[1], str) or r[1] >= 500 for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
