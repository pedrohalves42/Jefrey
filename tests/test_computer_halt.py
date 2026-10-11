import asyncio

import pytest

from src.jefrey.core import halt as H
from src.jefrey.core.tool_runtime import ToolRuntime


def run(c):
    return asyncio.run(c)


@pytest.fixture(autouse=True)
def limpo():
    H.clear()
    yield
    H.clear()


class Ferramenta:
    name = "open_app"
    description = "x"

    def __init__(self):
        self.chamadas = 0

    async def ainvoke(self, payload):
        self.chamadas += 1
        return "ok"


def test_parar_tudo_bloqueia_ferramentas_do_computador_e_so_elas():
    f = Ferramenta()
    rt = ToolRuntime(user_id="ana", thread_id="t", resolver=lambda n: f if n == "open_app" else None)
    H.request_halt()
    out = run(rt.run("open_app", {"name": "word"}))
    assert out.status == "halted" and "parei" in out.content.lower() and f.chamadas == 0
    H.clear()
    assert run(rt.run("open_app", {"name": "word"})).status == "ok" and f.chamadas == 1


def test_parada_vale_so_por_um_tempo(monkeypatch):
    t = [1000.0]
    monkeypatch.setattr(H, "_now", lambda: t[0])
    H.request_halt()
    assert H.is_halted()
    t[0] += H.HALT_SECONDS + 1
    assert not H.is_halted()


def test_ferramenta_que_nao_e_do_computador_nao_e_bloqueada():
    class Nota:
        name = "list_notes"
        description = "x"

        async def ainvoke(self, payload):
            return "[]"
    rt = ToolRuntime(user_id="ana", thread_id="t", resolver=lambda n: Nota() if n == "list_notes" else None)
    H.request_halt()
    assert run(rt.run("list_notes", {})).status == "ok"


def test_nova_pergunta_da_pessoa_limpa_a_parada():
    from src.jefrey.core import agent_loop as AL
    H.request_halt()
    AL.begin_turn()
    assert not H.is_halted()


def test_rota_de_parada_exige_login_e_aciona_a_flag():
    from fastapi import HTTPException
    from src.jefrey.api import halt_routes as HR

    class R:
        def __init__(self, uid):
            self.state = type("S", (), {"user_id": uid})()
    with pytest.raises(HTTPException):
        run(HR.halt(R(None)))
    assert run(HR.halt(R("ana")))["halted"] is True and H.is_halted()


def test_atalho_global_de_parada(monkeypatch):
    from src.jefrey.native import hotkey, launcher as L
    monkeypatch.setenv("JEFREY_NO_HOTKEY", "1")
    assert L.start_halt_hotkey() is None
    monkeypatch.delenv("JEFREY_NO_HOTKEY")
    visto = {}
    monkeypatch.setattr(hotkey, "start_hotkey", lambda cb, spec=None: visto.update(cb=cb, spec=spec) or (lambda: None))
    assert L.start_halt_hotkey() is not None
    assert visto["spec"] == "ctrl+alt+p" and visto["cb"] is H.request_halt and hotkey.parse_hotkey("ctrl+alt+p") is not None
