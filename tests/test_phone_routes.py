"""Rotas do celular (na tela do computador): so logado; nada liga sozinho; QR leva o codigo no fragmento."""
import asyncio

import pytest
from fastapi import HTTPException

from src.jefrey.api import phone_routes as PR
from src.jefrey.adapters.outbound.phone_env import PhoneService


class Req:
    def __init__(self, uid="pedro"):
        self.state = type("S", (), {"user_id": uid})()


@pytest.fixture
def svc(monkeypatch):
    s = PhoneService(app_factory=lambda *a: None)
    monkeypatch.setattr(PR, "shared_service", lambda: s)

    def fake_start():
        s.enabled, s.ip = True, "192.168.0.5"
        return True

    monkeypatch.setattr(s, "start", fake_start)
    return s


def test_sem_login_nega(svc):
    with pytest.raises(HTTPException) as e:
        asyncio.run(PR.state(Req("anonymous")))
    assert e.value.status_code == 401


def test_nasce_desligado(svc):
    assert asyncio.run(PR.state(Req()))["enabled"] is False


def test_pareamento_exige_ligado(svc):
    with pytest.raises(HTTPException) as e:
        asyncio.run(PR.pairing(Req()))
    assert e.value.status_code == 409


def test_qr_com_codigo_no_fragmento(svc, monkeypatch):
    asyncio.run(PR.set_enabled(Req(), PR.EnabledBody(enabled=True)))
    seen = {}
    monkeypatch.setattr(PR, "qr_svg", lambda link: seen.setdefault("link", link) and "<svg/>")
    r = asyncio.run(PR.pairing(Req()))
    assert r["expires_in"] == 300 and r["qr_svg"] == "<svg/>"
    assert seen["link"].startswith("http://192.168.0.5:8765/#c=") and "?" not in seen["link"]


def test_desligar_revoga_todos(svc):
    asyncio.run(PR.set_enabled(Req(), PR.EnabledBody(enabled=True)))
    tok = svc.book.redeem(svc.book.issue_code("pedro")[0])
    assert svc.book.check(tok)
    asyncio.run(PR.set_enabled(Req(), PR.EnabledBody(enabled=False)))
    assert svc.book.check(tok) is None and svc.url() is None


def test_sem_rede_local_avisa(monkeypatch):
    s = PhoneService(app_factory=lambda *a: None)
    monkeypatch.setattr(PR, "shared_service", lambda: s)
    import src.jefrey.adapters.outbound.phone_env as PE
    monkeypatch.setattr(PE, "lan_ip", lambda: None)
    with pytest.raises(HTTPException) as e:
        asyncio.run(PR.set_enabled(Req(), PR.EnabledBody(enabled=True)))
    assert e.value.status_code == 409


def test_qr_real_gera_svg():
    from src.jefrey.adapters.outbound.phone_env import qr_svg

    assert qr_svg("http://192.168.0.5:8765/#c=12345678").startswith("<svg")
