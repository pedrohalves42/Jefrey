"""Testa os FLUXOS reais do Jefrey aberto (conversa, ferramentas, lembretes, notas, aprendizado, aprovacao, voz ida-e-volta...).

Uso:  python scripts/audit_flows.py [http://127.0.0.1:8000]
Usa um usuario de teste ("auditoria") separado do seu e apaga tudo dele no fim. Gasta poucas chamadas de IA.
Saida: OK / FALHOU / AVISO por fluxo, com o motivo.
"""
from __future__ import annotations

import json
import sys
import time

import httpx

USER = "auditoria"
Result = tuple[str, str, str]


def chat(c: httpx.Client, h: dict, text: str, thread: str = "auditoria", approve: str | None = None) -> dict:
    """Manda uma mensagem e junta os eventos. approve='approved'|'rejected' decide o primeiro pedido de aprovacao."""
    out = {"text": "", "tools": [], "approval": None, "error": "", "secs": 0.0}
    t0 = time.perf_counter()
    decided = False
    with c.stream("POST", "/chat/stream", headers=h, json={"message": text, "thread_id": thread}) as r:
        for line in r.iter_lines():
            if not line.startswith("data:"):
                continue
            try:
                ev = json.loads(line[5:])
            except ValueError:
                continue
            t = ev.get("type")
            if t == "token":
                out["text"] += ev.get("content", "")
            elif t == "tool_start":
                out["tools"].append(ev.get("tool"))
            elif t == "approval_required":
                out["approval"] = ev
                if approve and not decided:
                    decided = True
                    c2 = httpx.Client(base_url=str(c.base_url), timeout=30)
                    c2.post(f"/approvals/{ev['approval_id']}/decide", headers=h, json={"decision": approve, "decided_by": "auditoria"})
            elif t == "error":
                out["error"] = ev.get("message", "erro")
    out["secs"] = round(time.perf_counter() - t0, 1)
    return out


def run(base: str) -> list[Result]:
    res: list[Result] = []

    def add(level: str, name: str, detail: str = "") -> None:
        res.append((level, name, detail))

    with httpx.Client(base_url=base, timeout=90) as c:
        tok = c.post("/auth/dev-token", json={"user_id": USER}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        g = lambda p, **k: c.get(p, headers=h, **k)  # noqa: E731
        try:
            # --- conversa e ferramentas simples
            r = chat(c, h, "Oi! Responda só: tudo certo?")
            add("OK" if r["text"].strip() and not r["error"] else "FALHOU", "conversa simples", f"{r['secs']} s · {r['text'][:50]!r}" if r["text"] else r["error"] or "sem resposta")
            r = chat(c, h, "Que horas são?")
            add("OK" if ":" in r["text"] and "current_time" in r["tools"] else "FALHOU", "hora (sem IA)", f"{r['secs']} s · {r['text'][:40]!r}")
            r = chat(c, h, "quanto é 12 vezes 7")
            add("OK" if "84" in r["text"] else "FALHOU", "calculadora (sem IA)", r["text"][:40])

            # --- lembretes: criar, listar, apagar
            r = chat(c, h, "Me lembra de beber água daqui a 3 horas")
            lst = g("/reminders").json()
            items = lst.get("reminders", lst if isinstance(lst, list) else [])
            found = [i for i in items if "água" in json.dumps(i, ensure_ascii=False).lower() or "agua" in json.dumps(i).lower()]
            add("OK" if found else "FALHOU", "lembrete criado pela conversa", r["text"][:70] or "sem resposta")
            for i in found:
                c.delete(f"/reminders/{i['id']}", headers=h)
            add("OK" if not [i for i in (g('/reminders').json().get('reminders', [])) if i in found] else "FALHOU", "lembrete apagado")

            # --- notas
            chat(c, h, "Anote que eu gosto de café sem açúcar")
            r = chat(c, h, "O que você sabe sobre café?")
            add("OK" if "café" in r["text"].lower() or "cafe" in r["text"].lower() else "AVISO", "notas e memoria (guardar e achar)", r["text"][:70])

            # --- aprendizado (ensinar, ver, esquecer)
            t = c.post("/learning", headers=h, json={"text": "Meu time é o Flamengo", "kind": "gosto"})
            facts = g("/learning").json().get("facts", [])
            add("OK" if t.status_code == 200 and any("Flamengo" in f["text"] for f in facts) else "FALHOU", "aprendizado: ensinar", f"HTTP {t.status_code}")
            sugg = g("/today/interests").json().get("suggested", [])
            add("OK" if "esportes" in sugg else "AVISO", "assuntos sugeridos pelo que aprendeu", str(sugg))
            for f in facts:
                c.delete(f"/learning/{f['id']}", headers=h)
            add("OK" if not g("/learning").json().get("facts") else "FALHOU", "aprendizado: esquecer")

            # --- Google nao conectado: mensagens claras (nunca erro tecnico)
            for label, q, key in (("agenda", "O que tenho na agenda hoje?", "agenda"), ("tarefas", "Quais são minhas tarefas?", "Conex"), ("contatos", "Qual o telefone da Maria?", "Conex")):
                r = chat(c, h, q)
                bad = any(w in r["text"].lower() for w in ("traceback", "exception", "typeerror", "error:"))
                add("FALHOU" if bad or not r["text"].strip() else "OK", f"sem Google: {label}", r["text"][:80])

            # --- WhatsApp por pedido: so com aprovacao e mostrando o texto
            r = chat(c, h, "Manda pro Arnaldo no WhatsApp que eu chego às 8", approve="rejected")
            ap = r["approval"] or {}
            add("OK" if ap and "Arnaldo" in (ap.get("detail") or "") else "FALHOU", "WhatsApp por pedido pede aprovacao com o texto", (ap.get("detail") or r["text"] or "sem aprovacao")[:90])
            r = chat(c, h, "Manda pro Arnaldo no WhatsApp que eu chego às 9", approve="approved")
            add("OK" if "Não achei" in r["text"] or "Na fila" in r["text"] else "AVISO", "WhatsApp aprovado sem conversa conhecida", r["text"][:90])

            # --- web e clima
            r = chat(c, h, "Pesquise na internet qual é a capital da Austrália")
            add("OK" if any(w in r["text"].lower() for w in ("canberra", "camberra")) else "AVISO", "pesquisa na web", f"{r['secs']} s · {r['text'][:60]!r}")
            r = chat(c, h, "Como está o clima em Balneário Piçarras agora?")
            add("OK" if any(ch.isdigit() for ch in r["text"]) else "AVISO", "clima", f"{r['secs']} s · {r['text'][:60]!r}")

            # --- voz ida e volta: fala -> escuta
            sp = c.post("/voice/speak", headers=h, json={"text": "Olá, este é um teste de voz do Jefrey.", "engine": "local"})
            if sp.status_code == 200:
                tr = c.post("/stt", headers=h, files={"audio": ("fala.wav", sp.content, "audio/wav")}, timeout=120)
                txt = (tr.json().get("text") or tr.json().get("transcript") or "") if tr.status_code == 200 else ""
                add("OK" if "teste" in txt.lower() else "FALHOU", "voz ida e volta (falar e entender)", f"HTTP {tr.status_code} · {txt[:60]!r}")
            else:
                add("FALHOU", "voz local (falar)", f"HTTP {sp.status_code}")

            # --- telas de dados
            for path, name in (("/briefing", "resumo do dia"), ("/privacy/summary", "privacidade: resumo"), ("/privacy/export", "privacidade: exportar"), ("/skills", "ferramentas"), ("/approvals/pending", "aprovacoes pendentes")):
                rr = g(path)
                add("OK" if rr.status_code == 200 else "FALHOU", name, f"HTTP {rr.status_code}")
        finally:
            er = c.post("/privacy/erase", headers=h, json={"confirm": "APAGAR"})
            add("OK" if er.status_code in (200, 204) else "AVISO", "limpeza do usuario de teste", f"HTTP {er.status_code}")
    return res


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    res = run(base)
    for level, name, detail in res:
        print(f"{level:<7}{name}" + (f": {detail}" if detail else ""))
    bad = sum(1 for r in res if r[0] == "FALHOU")
    print(f"\n{sum(1 for r in res if r[0] == 'OK')} OK · {sum(1 for r in res if r[0] == 'AVISO')} aviso(s) · {bad} falha(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
