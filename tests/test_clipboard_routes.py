"""Tarefa 6: API da area de transferencia (so logado; desligada por padrao; oferta so com texto ja observado)."""
import asyncio

import pytest
from fastapi import HTTPException

from src.jefrey.api import clipboard_routes as CR
from src.jefrey.application.clipboard import OfferStore

EN = "The quick brown fox jumps over the lazy dog and keeps running through the forest."


def run(c):
    return asyncio.run(c)


class Req:
    def __init__(self, uid="pedro"):
        self.state = type("S", (), {"user_id": uid})()


@pytest.fixture(autouse=True)
def loja(tmp_path, monkeypatch):
    s = OfferStore(tmp_path / "c.json")
    monkeypatch.setattr(CR, "shared_store", lambda: s)
    return s


def test_comeca_desligada_e_sem_oferta():
    assert run(CR.state(Req())) == {"enabled": False, "offer": None}


def test_ligar_e_ver_a_oferta_com_texto_curto_para_a_tela(loja):
    run(CR.set_enabled(Req(), CR.EnabledBody(enabled=True)))
    loja.set({"text": EN * 10, "offers": ["traduzir", "resumir"]})
    out = run(CR.state(Req()))
    assert out["enabled"] is True and out["offer"]["offers"] == ["traduzir", "resumir"]
    assert len(out["offer"]["preview"]) <= 200  # a tela so ve um trecho


def test_pedido_da_acao_e_dispensar(loja):
    loja.set({"text": EN, "offers": ["traduzir"]})
    assert "<dados>" in run(CR.prompt(Req(), CR.ActionBody(action="traduzir")))["prompt"]
    with pytest.raises(HTTPException) as e:
        run(CR.prompt(Req(), CR.ActionBody(action="apagar")))
    assert e.value.status_code == 422
    run(CR.dismiss(Req()))
    assert run(CR.state(Req()))["offer"] is None


def test_sem_login_nada_funciona():
    with pytest.raises(HTTPException) as e:
        run(CR.state(Req("anonymous")))
    assert e.value.status_code == 401
