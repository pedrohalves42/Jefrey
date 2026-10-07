"""Mini cliente CDP para testar a janela do app: python cdp.py PORTA 'expressao js' [indice_da_pagina]"""
import asyncio, json, sys, httpx, websockets


async def main(port, expr, idx=0):
    pages = [p for p in httpx.get(f"http://127.0.0.1:{port}/json", timeout=30).json() if p.get("type") == "page"]
    for i, p in enumerate(pages):
        print(i, p["title"], p["url"])
    if isinstance(idx, str):
        idx = next(i for i, p in enumerate(pages) if str(idx) in p["url"] and "orb" not in p["url"])
    ws_url = pages[idx]["webSocketDebuggerUrl"]
    async with websockets.connect(ws_url, max_size=50_000_000) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "awaitPromise": True, "returnByValue": True, "userGesture": True}}))
        while True:
            m = json.loads(await ws.recv())
            if m.get("id") == 1:
                print(json.dumps(m.get("result"), ensure_ascii=False)[:3000])
                break


asyncio.run(main(sys.argv[1], sys.argv[2], (int(sys.argv[3]) if len(sys.argv[3]) < 3 else sys.argv[3]) if len(sys.argv) > 3 else 0))
