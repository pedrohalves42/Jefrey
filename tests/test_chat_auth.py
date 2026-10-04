"""Chat exige login por padrao; modo anonimo e opt-in explicito."""
import pytest
from fastapi.testclient import TestClient

from src.jefrey.api.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


BODY = {"message": "oi", "thread_id": "t1"}


@pytest.mark.parametrize("method,path", [("post", "/chat"), ("post", "/chat/stream"), ("get", "/chat/status/t1")])
def test_sem_token_401_por_padrao(client, monkeypatch, method, path):
    monkeypatch.delenv("JEFREY_API__ALLOW_ANONYMOUS_CHAT", raising=False)
    r = getattr(client, method)(path, **({"json": BODY} if method == "post" else {}))
    assert r.status_code == 401


def test_com_token_passa_da_autenticacao(client, monkeypatch):
    monkeypatch.delenv("JEFREY_API__ALLOW_ANONYMOUS_CHAT", raising=False)
    tok = client.post("/auth/dev-token").json()["access_token"]
    r = client.post("/chat", json={"message": "", "thread_id": "t1"}, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 422  # passou da auth; falhou so na validacao do corpo


def test_opt_in_anonimo_so_com_variavel(client, monkeypatch):
    monkeypatch.setenv("JEFREY_API__ALLOW_ANONYMOUS_CHAT", "true")
    r = client.post("/chat", json={"message": "", "thread_id": "t1"})
    assert r.status_code == 422  # sem token, mas permitido -> chega na validacao
