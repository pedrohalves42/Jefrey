"""Mede a velocidade das respostas do Jefrey ja aberto: tempo ate a primeira palavra e tempo total, por tipo de pergunta.

Uso:  python scripts/bench_chat.py [http://127.0.0.1:8000] [usuario] [repeticoes]
Nada de chave na saida. Usa uma conversa de teste (thread "bench"), que nao mistura com as suas.
"""
from __future__ import annotations

import json
import statistics
import sys
import time

import httpx

QUESTIONS = [
    ("oi simples", "Oi, tudo bem?"),
    ("hora (sem IA)", "Que horas são?"),
    ("pergunta curta", "Qual a capital da França?"),
    ("explicacao", "Explique em três frases o que é inflação."),
    ("lembrete (ferramenta)", "Me lembra de beber água daqui a 2 horas"),
    ("sobre mim (memoria)", "O que você sabe sobre mim?"),
    ("agenda (Google)", "O que tenho na agenda hoje?"),
]


def ask(c: httpx.Client, auth: dict, text: str) -> tuple[float, float, int]:
    """(segundos ate o primeiro texto, segundos no total, caracteres)."""
    t0 = time.perf_counter()
    first = 0.0
    chars = 0
    with c.stream("POST", "/chat/stream", headers=auth, json={"message": text, "thread_id": "bench"}) as r:
        for line in r.iter_lines():
            if not line.startswith("data:"):
                continue
            try:
                ev = json.loads(line[5:].strip())
            except ValueError:
                continue
            piece = ev.get("text") or ev.get("token") or ev.get("content") or ""
            if isinstance(piece, str) and piece:
                if not first:
                    first = time.perf_counter() - t0
                chars += len(piece)
    return first, time.perf_counter() - t0, chars


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    user = sys.argv[2] if len(sys.argv) > 2 else "demo"
    reps = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    with httpx.Client(base_url=base, timeout=120) as c:
        tok = c.post("/auth/dev-token", json={"user_id": user}).json()["access_token"]
        auth = {"Authorization": f"Bearer {tok}"}
        print(f"{'pergunta':<26}{'1a palavra':>12}{'total':>9}{'chars':>7}")
        slow = 0
        for label, q in QUESTIONS:
            firsts, totals, sizes = [], [], []
            for _ in range(reps):
                f, t, n = ask(c, auth, q)
                firsts.append(f or t)
                totals.append(t)
                sizes.append(n)
            f, t = statistics.median(firsts), statistics.median(totals)
            flag = "  <- lenta" if f > 4 else ""
            slow += 1 if f > 4 else 0
            print(f"{label:<26}{f:>10.1f} s{t:>7.1f} s{int(statistics.median(sizes)):>6}{flag}")
    print(f"\n{slow} pergunta(s) com a primeira palavra acima de 4 s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
