"""Bateria unica no Jefrey JA ABERTO: verificacao do instalado, WhatsApp, conectividade e perguntas reais com tempo.

Uso:  python scripts/e2e_installed.py [http://127.0.0.1:8000]
Saida: relatorio em texto e JSON em data/e2e/AAAA-MM-DD-HHMM.json; codigo 0 so se tudo obrigatorio passou.
Nunca imprime tokens nem chaves. As perguntas nao criam nada (so leitura e conversa).
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
LIMIT_S = 15.0
QUESTIONS = [
    ("resumo do dia", "Bom dia, o que eu tenho pra hoje?", "daily_summary"),
    ("noticias", "Quais as ultimas noticias sobre inteligencia artificial?", "news_brief"),
    ("desfazer", "Desfaz isso", "undo_last"),
    ("conversa", "Me sugere um jantar rapido pra hoje", None),
]
SCRIPTS = ["verify_installed.py", "audit_whatsapp.py", "check_connectivity.py"]


def summarize(results: list[dict]) -> dict:
    """Obrigatorio: scripts passam e cada pergunta responde (sem erro). Tempo acima do limite e AVISO, nao falha."""
    failed = [r["name"] for r in results if not r["ok"]]
    slow = [r["name"] for r in results if r.get("seconds") and r["seconds"] > LIMIT_S]
    return {"ok": not failed, "failed": failed, "slow": slow}


def run_script(name: str, base: str) -> dict:
    t = time.time()
    p = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts" / name), base], capture_output=True, text=True, encoding="utf-8", errors="replace")
    last = (p.stdout.strip().splitlines() or [""])[-1]
    return {"name": name, "ok": p.returncode == 0 or "0 falha" in last, "seconds": round(time.time() - t, 1), "detail": last[:160]}


def ask(base: str, label: str, text: str, tool: str | None) -> dict:
    t0 = time.time()
    seen, answer, err = [], "", ""
    try:
        tok = httpx.post(base + "/auth/dev-token", json={"user_id": "demo"}, timeout=15).json()["access_token"]
        with httpx.stream("POST", base + "/chat/stream", headers={"Authorization": "Bearer " + tok},
                          json={"message": text, "thread_id": f"e2e-{int(t0)}"}, timeout=90) as r:
            for line in r.iter_lines():
                if not line.startswith("data:"):
                    continue
                try:
                    d = json.loads(line[5:])
                except ValueError:
                    continue
                if d.get("type") == "token":
                    answer += d.get("content", "")
                elif d.get("type") == "tool_start":
                    seen.append(d.get("tool"))
                elif d.get("type") == "error":
                    err = d.get("message", "erro")
    except Exception as e:
        err = type(e).__name__
    secs = round(time.time() - t0, 1)
    ok = bool(answer.strip()) and not err and (tool is None or tool in seen)
    return {"name": f"pergunta: {label}", "ok": ok, "seconds": secs, "detail": (err or answer.strip().replace("\n", " ")[:120])}


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    results = [run_script(s, base) for s in SCRIPTS] + [ask(base, *q) for q in QUESTIONS]
    for r in results:
        print(("OK     " if r["ok"] else "FALHOU ") + f"{r['name']} ({r['seconds']} s): {r['detail']}")
    s = summarize(results)
    print(f"\n{'TUDO OK' if s['ok'] else 'FALHAS: ' + ', '.join(s['failed'])}" + (f" | lentos (>{LIMIT_S:.0f} s): {', '.join(s['slow'])}" if s["slow"] else ""))
    out = ROOT / "data" / "e2e"
    out.mkdir(parents=True, exist_ok=True)
    (out / (datetime.now().strftime("%Y-%m-%d-%H%M") + ".json")).write_text(json.dumps({"results": results, "summary": s}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if s["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
