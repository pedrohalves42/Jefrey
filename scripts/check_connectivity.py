"""Testa tudo que o Jefrey liga com o mundo de fora, no programa JA ABERTO (nada de chave ou token na saida).

Uso:  python scripts/check_connectivity.py [http://127.0.0.1:8000] [usuario]
O usuario padrao e o da tela do app ("demo"). Sai com codigo 0 so se todos os itens obrigatorios passaram.
Itens "opcionais" (voz da nuvem, Alexa, WhatsApp sem mensagem recente) aparecem como AVISO, nao como falha.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

Result = tuple[str, str, str]  # (nivel OK|AVISO|FALHOU, nome, detalhe)


def run(base: str = "http://127.0.0.1:8000", user: str = "demo", transport: httpx.BaseTransport | None = None) -> list[Result]:
    out: list[Result] = []

    def add(level: str, name: str, detail: str = "") -> None:
        out.append((level, name, detail))

    with httpx.Client(base_url=base, timeout=45, transport=transport) as c:
        try:
            h = c.get("/health").json()
            add("OK", "servidor", f"v{h.get('version')} · {h.get('build')} · {h.get('mode')}")
        except Exception as e:
            return [("FALHOU", "servidor", f"nao respondeu ({type(e).__name__})")]
        try:
            tok = c.post("/auth/dev-token", json={"user_id": user}).json()["access_token"]
        except Exception as e:
            return out + [("FALHOU", "login local", type(e).__name__)]
        auth = {"Authorization": f"Bearer {tok}"}

        def get(path: str, **kw) -> httpx.Response:
            return c.get(path, headers=auth, **kw)

        # --- cerebro de IA (uma pergunta curta de verdade)
        try:
            t0 = time.time()
            with c.stream("POST", "/chat/stream", headers=auth, json={"message": "Responda só com a palavra: ok", "thread_id": "teste_conectividade"}) as r:
                body = "".join(r.iter_text())
            ok = r.status_code == 200 and ("data:" in body) and "error" not in body[:200].lower()
            add("OK" if ok else "FALHOU", "cerebro de IA (chat)", f"{round(time.time() - t0, 1)} s" if ok else f"HTTP {r.status_code}: {body[:120]!r}")
        except Exception as e:
            add("FALHOU", "cerebro de IA (chat)", type(e).__name__)
        try:
            b = get("/brains").json()
            brains = b.get("brains", b if isinstance(b, list) else [])
            conectados = [x.get("id") for x in brains if isinstance(x, dict) and (x.get("connected") or x.get("configured"))]
            add("OK" if conectados else "AVISO", "cerebros conectados", ", ".join(map(str, conectados)) or "nenhum")
        except Exception as e:
            add("AVISO", "cerebros conectados", type(e).__name__)

        # --- Google
        try:
            g = get("/connections/google").json()
            if g.get("connected"):
                add("OK", "Google conectado", f"{g.get('email') or ''} · {', '.join(g.get('services', []))}")
            else:
                add("FALHOU", "Google conectado", "nao conectado")
            d = g.get("diagnosis") or {}
            if d and not d.get("ok", True):
                add("AVISO", "Google: configuracao", str(d.get("advice", ""))[:140])
        except Exception as e:
            add("FALHOU", "Google conectado", type(e).__name__)

        # --- painel Hoje (agenda do Google, feeds de noticias, cotacoes, tempo)
        try:
            t = get("/today").json()["sections"]
            for k, label in (("agenda", "Google Agenda"), ("news", "noticias (g1)"), ("market", "cotacoes"), ("weather", "tempo (Open-Meteo)"), ("foryou", "Para voce")):
                s = (t.get(k) or {}).get("status", "?")
                add("OK" if s in ("ok", "parcial") else ("AVISO" if s in ("sem_interesses", "falta_regiao", "vazio") else "FALHOU"), f"hoje: {label}", s)
        except Exception as e:
            add("FALHOU", "painel Hoje", type(e).__name__)

        # --- WhatsApp (extensao do Chrome)
        try:
            w = get("/wa/status").json()
            devs = w.get("devices", [])
            if not devs:
                add("FALHOU", "WhatsApp: extensao pareada", "nenhum aparelho")
            else:
                last = max((d.get("last_seen") or "" for d in devs), default="")
                try:
                    age = (datetime.now(timezone.utc).replace(tzinfo=None) - datetime.fromisoformat(last)).total_seconds()
                except ValueError:
                    age = 1e9
                add("OK" if age < 120 else "AVISO", "WhatsApp: extensao falando com o Jefrey", f"visto ha {int(age)} s" if age < 1e8 else "nunca")
            add("OK", "WhatsApp: conversas", f"{len(w.get('chats', []))} conversa(s), {len(w.get('pending', []))} resposta(s) esperando voce")
        except Exception as e:
            add("FALHOU", "WhatsApp", type(e).__name__)

        # --- voz
        try:
            e = get("/voice/engines").json()
            engines = {x["id"]: x.get("available") for x in e.get("engines", [])}
            add("OK" if engines.get("local") or engines.get("cloud") else "FALHOU", "voz natural disponivel", ", ".join(k for k, v in engines.items() if v) or "nenhuma")
            sp = c.post("/voice/speak", headers=auth, json={"text": "Teste de voz do Jefrey."})
            add("OK" if sp.status_code == 200 and len(sp.content) > 2000 else "FALHOU", "voz: gerar fala", f"{sp.headers.get('x-voice-engine', '?')} · {len(sp.content)} bytes" if sp.status_code == 200 else f"HTTP {sp.status_code}")
        except Exception as e:
            add("FALHOU", "voz", type(e).__name__)
        try:
            st = get("/stt/status").json()
            add("OK" if st.get("ready", st.get("status") in ("ok", "ready", True)) else "AVISO", "ouvir (voz para texto)", json.dumps(st, ensure_ascii=False)[:100])
        except Exception as e:
            add("AVISO", "ouvir (voz para texto)", type(e).__name__)

        # --- atualizacoes, Alexa, janela
        try:
            u = get("/updates/check").json()
            add("OK", "atualizacoes", str(u.get("status") or u.get("message") or "ok")[:100])
        except Exception as e:
            add("AVISO", "atualizacoes", type(e).__name__)
        try:
            a = get("/alexa").json()
            add("OK" if a.get("configured") or a.get("connected") else "AVISO", "Alexa", "configurada" if a.get("configured") or a.get("connected") else "nao configurada")
        except Exception as e:
            add("AVISO", "Alexa", type(e).__name__)
        try:
            add("OK" if get("/system/shell").json().get("window") else "AVISO", "janela propria do app", "ativa" if get("/system/shell").json().get("window") else "aberto no navegador")
        except Exception as e:
            add("AVISO", "janela propria do app", type(e).__name__)

    # --- extensao do Chrome atualizada na pasta que o Chrome carrega
    try:
        pasta = Path.home() / "Documents" / "Jefrey" / "extensao-chrome" / "core.js"
        add("OK" if pasta.is_file() and "openChat" in pasta.read_text(encoding="utf-8") else "AVISO", "extensao do Chrome: versao nova na pasta", str(pasta.parent))
    except OSError as e:
        add("AVISO", "extensao do Chrome: versao nova na pasta", type(e).__name__)
    return out


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    user = sys.argv[2] if len(sys.argv) > 2 else "demo"
    res = run(base, user)
    for level, name, detail in res:
        print(f"{level:<7}{name}" + (f": {detail}" if detail else ""))
    bad = [n for lv, n, _ in res if lv == "FALHOU"]
    warn = [n for lv, n, _ in res if lv == "AVISO"]
    print(f"\n{sum(1 for r in res if r[0] == 'OK')} OK · {len(warn)} aviso(s) · {len(bad)} falha(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
