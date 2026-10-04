"""Login Google: state e PKCE obrigatorios, de uso unico e com validade (antes o state nem era conferido)."""
import base64
import hashlib
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from src.jefrey.api import auth
from src.jefrey.api.main import app


@pytest.fixture()
def c(monkeypatch):
    monkeypatch.setattr(auth, "_get_oauth_credentials", lambda: {
        "client_id": "cid", "client_secret": "csec", "redirect_uri": "http://localhost:8000/auth/google/callback"})
    auth._google_states.clear()
    return TestClient(app)


def login(c):
    r = c.get("/auth/google/login")
    assert r.status_code == 200
    q = {k: v[0] for k, v in parse_qs(urlparse(r.json()["auth_url"]).query).items()}
    return q


def test_login_gera_state_e_pkce_s256(c):
    q = login(c)
    assert len(q["state"]) >= 24 and q["code_challenge_method"] == "S256"
    verifier, _ = auth._google_states[q["state"]]
    assert q["code_challenge"] == base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


@pytest.mark.parametrize("params", [{"code": "x"}, {"code": "x", "state": "inventado"}, {"state": "s"}, {}])
def test_retorno_sem_state_valido_e_recusado(c, params):
    r = c.get("/auth/google/callback", params=params)
    assert r.status_code == 400 and "state" in r.json()["detail"]


def test_state_expirado_e_recusado(c):
    q = login(c)
    v, _ = auth._google_states[q["state"]]
    auth._google_states[q["state"]] = (v, time.time() - 1)
    assert c.get("/auth/google/callback", params={"code": "x", "state": q["state"]}).status_code == 400


def test_state_valido_passa_e_envia_o_code_verifier_ao_google(c, monkeypatch):
    q = login(c)
    verifier, _ = auth._google_states[q["state"]]
    seen = {}

    def handler(req):
        if "oauth2.googleapis.com/token" in str(req.url):
            seen.update(dict(x.split("=", 1) for x in req.content.decode().split("&")))
            return httpx.Response(400, json={"error": "invalid_grant"})  # para no meio: so queremos ver o envio
        return httpx.Response(404)
    real = httpx.AsyncClient

    class Fake(real):
        def __init__(self, *a, **kw):
            super().__init__(*a, transport=httpx.MockTransport(handler), **kw)
    monkeypatch.setattr(auth.httpx, "AsyncClient", Fake)
    r = c.get("/auth/google/callback", params={"code": "abc", "state": q["state"]})
    assert r.status_code == 400 and "invalid_grant" in r.json()["detail"]  # passou pelo state e chegou ao Google
    assert seen.get("code_verifier") == verifier and seen.get("code") == "abc"


def test_state_e_de_uso_unico(c, monkeypatch):
    q = login(c)
    monkeypatch.setattr(auth.httpx, "AsyncClient", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("nao deveria chegar")))
    try:
        c.get("/auth/google/callback", params={"code": "a", "state": q["state"]})
    except Exception:
        pass
    again = c.get("/auth/google/callback", params={"code": "a", "state": q["state"]})
    assert again.status_code == 400 and "state" in again.json()["detail"]


def test_teto_de_logins_pendentes(c):
    for _ in range(80):
        auth._remember_google_state(f"s{_}", "v")
    assert len(auth._google_states) <= 50
