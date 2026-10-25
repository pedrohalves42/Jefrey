"""Abre cada tela do Jefrey na janela do app (porta de inspecao) e anota erros do console, excecoes, pedidos que falharam e quantos pedidos a tela faz.

Uso:  (abra o Jefrey com JEFREY_WEBVIEW_DEBUG_PORT=9444)   python scripts/dev/ui_crawl.py [porta] [rotas separadas por virgula]
Termina voltando a janela para a tela principal. Nao clica em nada que mude dados.
"""
from __future__ import annotations

import asyncio
import json
import sys

import httpx
import websockets

ROUTES = ["/", "/hoje", "/conexoes", "/aprender", "/aprendi", "/configuracoes", "/privacidade", "/ajuda", "/estudos", "/memoria", "/skills", "/avancado", "/termos", "/orb"]


async def crawl(port: str, routes: list[str]) -> int:
    pages = [p for p in httpx.get(f"http://127.0.0.1:{port}/json", timeout=20).json() if p.get("type") == "page" and "127.0.0.1:8000" in p["url"] and "/orb" not in p["url"]]
    if not pages:
        print("nenhuma pagina do Jefrey encontrada na porta", port)
        return 2
    problems = 0
    async with websockets.connect(pages[0]["webSocketDebuggerUrl"], max_size=50_000_000) as ws:
        mid = 0
        events: list[dict] = []

        async def send(method: str, params: dict | None = None) -> dict:
            nonlocal mid
            mid += 1
            my = mid
            await ws.send(json.dumps({"id": my, "method": method, "params": params or {}}))
            while True:
                m = json.loads(await ws.recv())
                if m.get("id") == my:
                    return m.get("result", {})
                events.append(m)

        async def drain(seconds: float) -> None:
            end = asyncio.get_event_loop().time() + seconds
            while True:
                left = end - asyncio.get_event_loop().time()
                if left <= 0:
                    return
                try:
                    events.append(json.loads(await asyncio.wait_for(ws.recv(), timeout=left)))
                except asyncio.TimeoutError:
                    return

        for d in ("Page", "Runtime", "Network", "Log"):
            await send(f"{d}.enable")
        print(f"{'tela':<16}{'pedidos':>8}  {'erros':>5}  observacoes")
        for r in routes:
            events.clear()
            await send("Page.navigate", {"url": f"http://127.0.0.1:8000{r}?app=1"})
            await drain(5.5)
            reqs = [e for e in events if e.get("method") == "Network.requestWillBeSent" and "127.0.0.1:8000" in e["params"]["request"]["url"]
                    and not any(x in e["params"]["request"]["url"] for x in (".js", ".css", ".svg", ".png", ".woff"))]
            bad = [e for e in events if e.get("method") == "Network.responseReceived" and e["params"]["response"]["status"] >= 400]
            errs = [e for e in events if e.get("method") == "Runtime.exceptionThrown"
                    or (e.get("method") == "Runtime.consoleAPICalled" and e["params"]["type"] == "error")
                    or (e.get("method") == "Log.entryAdded" and e["params"]["entry"]["level"] == "error" and e["params"]["entry"].get("source") != "network")]
            notes = []
            for b in bad:
                u = b["params"]["response"]["url"].split("8000")[-1][:50]
                notes.append(f"{b['params']['response']['status']} {u}")
            for e in errs[:3]:
                if e["method"] == "Runtime.exceptionThrown":
                    notes.append("excecao: " + str(e["params"]["exceptionDetails"].get("exception", {}).get("description", e["params"]["exceptionDetails"].get("text", "")))[:90])
                elif e["method"] == "Runtime.consoleAPICalled":
                    notes.append("console: " + " ".join(str(a.get("value", a.get("description", ""))) for a in e["params"]["args"])[:90])
                else:
                    notes.append("log: " + str(e["params"]["entry"].get("text", ""))[:90])
            n_bad = len(bad) + len(errs)
            problems += 1 if n_bad else 0
            print(f"{r:<16}{len(reqs):>8}  {n_bad:>5}  " + ("; ".join(dict.fromkeys(notes)) if notes else "ok"))
        await send("Page.navigate", {"url": "http://127.0.0.1:8000/?app=1"})
    print(f"\n{len(routes) - problems}/{len(routes)} telas sem problema")
    return 1 if problems else 0


if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else "9444"
    rs = sys.argv[2].split(",") if len(sys.argv) > 2 else ROUTES
    sys.exit(asyncio.run(crawl(port, rs)))
