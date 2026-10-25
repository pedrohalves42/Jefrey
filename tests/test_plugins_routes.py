"""Rotas de plugins: so logado; aprovar exige o hash que a pessoa viu."""
import asyncio

import pytest
from fastapi import HTTPException

from src.jefrey.api import plugins_routes as PR
from src.jefrey.application.plugins import PluginStore


class Req:
    def __init__(self, uid="pedro"):
        self.state = type("S", (), {"user_id": uid})()


@pytest.fixture
def store(tmp_path, monkeypatch):
    d = tmp_path / "p"
    d.mkdir()
    (d / "x.py").write_text("y = 1\n", encoding="utf-8")
    s = PluginStore(d, tmp_path / "a.json")
    monkeypatch.setattr(PR, "shared_store", lambda: s)
    return s


def test_sem_login_nega(store):
    with pytest.raises(HTTPException) as e:
        asyncio.run(PR.listing(Req("anonymous")))
    assert e.value.status_code == 401


def test_aprova_so_com_o_hash_certo(store):
    h = asyncio.run(PR.listing(Req()))["plugins"][0]["sha256"]
    with pytest.raises(HTTPException) as e:
        asyncio.run(PR.approve("x", PR.ApproveBody(sha256="0" * 64), Req()))
    assert e.value.status_code == 409
    assert asyncio.run(PR.approve("x", PR.ApproveBody(sha256=h), Req()))["loaded"] == ["x"]
    assert asyncio.run(PR.revoke("x", Req()))["revoked"] is True
