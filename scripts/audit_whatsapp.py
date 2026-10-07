"""Faz o papel da extensao do WhatsApp contra o Jefrey aberto: pareia, manda a lista de conversas, o historico e um pedido na conversa
"com voce mesmo", e confere que a resposta volta na fila de envio. Usa um usuario de teste ("auditoria-wa") e apaga tudo no fim.

Uso:  python scripts/audit_whatsapp.py [http://127.0.0.1:8000]
"""
from __future__ import annotations

import sys
import time

import httpx

USER = "auditoria-wa"


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    res: list[tuple[str, str, str]] = []

    def add(level: str, name: str, detail: str = "") -> None:
        res.append((level, name, detail))
        print(f"{level:<7}{name}" + (f": {detail}" if detail else ""))

    with httpx.Client(base_url=base, timeout=60) as c:
        tok = c.post("/auth/dev-token", json={"user_id": USER}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        try:
            code = c.post("/wa/pairing", headers=h).json()["code"]
            pr = c.post("/wa/device/pair", json={"code": code, "label": "simulador"})
            add("OK" if pr.status_code == 200 else "FALHOU", "parear a extensao", f"HTTP {pr.status_code}")
            d = {"Authorization": "Bearer " + pr.json()["token"]}

            r = c.post("/wa/device/inbox", headers=d, json={"items": [
                {"title": "Maria", "preview": "vamos jantar hoje?", "unread": 2},
                {"title": "Família", "preview": "foto", "unread": 9, "group": True},
                {"title": "José", "preview": "", "unread": 0}]})
            add("OK" if r.status_code == 200 and r.json().get("new") == 1 else "FALHOU", "lista de conversas recebida", r.text[:60])
            inbox = c.get("/wa/inbox", headers=h).json()
            add("OK" if "Maria" in inbox["text"] and "Família" not in inbox["text"] else "FALHOU", "caixa de entrada (grupo fica de fora)", inbox["text"][:70].replace("\n", " "))

            c.post("/wa/device/inbound", headers=d, json={"chat": "Maria", "is_group": False, "messages": [], "context": []})
            r = c.post("/wa/device/history", headers=d, json={"chat": "Maria", "messages": [
                {"id": "m1", "text": "vamos jantar hoje?", "from_me": False}, {"id": "m2", "text": "bora, às 20h", "from_me": True}]})
            add("OK" if r.status_code == 200 and r.json().get("saved") == 2 else "FALHOU", "historico recebido", r.text[:60])

            def chat(text: str) -> str:
                out = ""
                with c.stream("POST", "/chat/stream", headers=h, json={"message": text, "thread_id": "auditoria-wa"}) as s:
                    for line in s.iter_lines():
                        if line.startswith("data:") and '"token"' in line:
                            import json

                            out += json.loads(line[5:]).get("content", "")
                return out

            t = chat("Tenho mensagem no WhatsApp?")
            add("OK" if "Maria" in t else "FALHOU", "Jefrey responde as mensagens novas", t[:70].replace("\n", " "))
            t = chat("O que a Maria me disse?")
            add("OK" if "jantar" in t else "FALHOU", "Jefrey le a conversa da Maria", t[:70].replace("\n", " "))

            r = c.post("/wa/device/command", headers=d, json={"chat": "Pedro (Você)", "id": "cmd-1", "text": "Que horas são?"})
            add("OK" if r.json().get("action") == "working" else "FALHOU", "pedido na conversa com voce mesmo aceito", r.text[:60])
            reply = ""
            for _ in range(60):
                time.sleep(1)
                out = c.get("/wa/device/poll", headers=d).json().get("send", [])
                mine = [m for m in out if m["chat"].startswith("Pedro")]
                if mine:
                    reply = mine[0]["text"]
                    break
            add("OK" if reply.startswith("🤖") and ":" in reply else "FALHOU", "resposta volta pela fila da extensao", reply[:70] or "nada em 60 s")
            again = c.post("/wa/device/command", headers=d, json={"chat": "Pedro (Você)", "id": "cmd-1", "text": "Que horas são?"})
            time.sleep(2)
            dup = [m for m in c.get("/wa/device/poll", headers=d).json().get("send", []) if m["chat"].startswith("Pedro") and m["text"] != reply]
            add("OK" if again.status_code == 200 and not dup else "FALHOU", "o mesmo pedido nao e respondido duas vezes")
            r = c.post("/wa/device/command", headers=d, json={"chat": "Maria", "id": "cmd-2", "text": "que horas são?"})
            add("OK" if r.json().get("action") == "none" else "FALHOU", "so a conversa com voce mesmo vira pedido", r.text[:60])
        finally:
            er = c.delete("/wa/data", headers=h)
            add("OK" if er.status_code == 200 else "AVISO", "limpeza do usuario de teste", f"HTTP {er.status_code}")
    bad = sum(1 for r in res if r[0] == "FALHOU")
    print(f"\n{sum(1 for r in res if r[0] == 'OK')} OK · {bad} falha(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
