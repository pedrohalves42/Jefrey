import importlib.util
from pathlib import Path

import httpx

_spec = importlib.util.spec_from_file_location("check_connectivity", Path(__file__).resolve().parents[1] / "scripts" / "check_connectivity.py")
CC = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CC)


def servidor(wa_visto="2999-01-01T00:00:00", google=True):
    def h(r: httpx.Request):
        p = r.url.path
        if p == "/health":
            return httpx.Response(200, json={"version": "9.9.9", "build": "x", "mode": "native"})
        if p == "/auth/dev-token":
            return httpx.Response(200, json={"access_token": "T"})
        if p == "/chat/stream":
            return httpx.Response(200, text='data: {"type":"token","text":"ok"}\n\n')
        if p == "/brains":
            return httpx.Response(200, json={"brains": [{"id": "openrouter", "connected": True}]})
        if p == "/connections/google":
            return httpx.Response(200, json={"connected": google, "email": "a@b.c", "services": ["calendar"]})
        if p == "/today":
            return httpx.Response(200, json={"sections": {"agenda": {"status": "ok"}, "news": {"status": "ok"}, "market": {"status": "ok"}, "weather": {"status": "ok"}, "foryou": {"status": "sem_interesses"}}})
        if p == "/wa/status":
            return httpx.Response(200, json={"devices": [{"last_seen": wa_visto}], "chats": [], "pending": []})
        if p == "/voice/engines":
            return httpx.Response(200, json={"engines": [{"id": "local", "available": True}]})
        if p == "/voice/speak":
            return httpx.Response(200, content=b"x" * 5000, headers={"X-Voice-Engine": "local"})
        if p == "/system/shell":
            return httpx.Response(200, json={"window": True})
        return httpx.Response(200, json={})
    return httpx.MockTransport(h)


def test_tudo_ok_e_sem_falhas():
    res = CC.run("http://x", "demo", transport=servidor())
    assert not [r for r in res if r[0] == "FALHOU"]
    assert ("OK", "Google conectado", "a@b.c · calendar") in res


def test_google_desconectado_e_falha_e_extensao_parada_e_aviso():
    res = CC.run("http://x", "demo", transport=servidor(wa_visto="2020-01-01T00:00:00", google=False))
    assert any(r[0] == "FALHOU" and r[1] == "Google conectado" for r in res)
    assert any(r[0] == "AVISO" and r[1].startswith("WhatsApp: extensao falando") for r in res)


def test_servidor_fora_do_ar_para_cedo():
    def fora(r):
        raise httpx.ConnectError("recusou")
    res = CC.run("http://x", "demo", transport=httpx.MockTransport(fora))
    assert res[0][0] == "FALHOU" and len(res) == 1
