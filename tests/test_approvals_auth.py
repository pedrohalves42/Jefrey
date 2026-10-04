"""/approvals aceita o JWT do usuario e NAO deixa X-User-Id personificar outro usuario."""
import uuid

import pytest
from fastapi.testclient import TestClient

from src.jefrey.api.main import app
from src.jefrey.core.config import get_settings


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _jwt(client, user):
    r = client.post("/auth/dev-token", json={"user_id": user})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_sem_token_401(client):
    assert client.get("/approvals/pending").status_code == 401


def test_token_lixo_401(client):
    assert client.get("/approvals/pending", headers={"Authorization": "Bearer a.b.c"}).status_code == 401


def test_usuario_com_jwt_lista_pendencias(client):
    r = client.get("/approvals/pending", headers=_jwt(client, "ana"))
    assert r.status_code == 200, r.text
    assert "pending" in r.json()


def test_decidir_inexistente_404_e_uuid_invalido_400(client):
    h = _jwt(client, "ana")
    assert client.post("/approvals/nao-e-uuid/decide", headers=h, json={"decision": "approved"}).status_code == 400
    assert client.post(f"/approvals/{uuid.uuid4()}/decide", headers=h, json={"decision": "approved"}).status_code == 404


def test_header_x_user_id_nao_personifica_usuario_jwt(client, monkeypatch):
    """Com JWT de 'ana', X-User-Id: 'bob' deve ser ignorado: a consulta e feita como 'ana'."""
    seen = {}

    from src.jefrey.core import hitl

    def fake_get_pending(self, thread_id=None, user_id=None):
        seen["user_id"] = user_id
        return []

    monkeypatch.setattr(hitl.ApprovalManager, "get_pending", fake_get_pending)
    h = {**_jwt(client, "ana"), "X-User-Id": "bob"}
    assert client.get("/approvals/pending", headers=h).status_code == 200
    assert seen["user_id"] == "ana"


def test_chave_de_servico_age_em_nome_do_x_user_id(client, monkeypatch):
    seen = {}
    from src.jefrey.core import hitl

    def fake_get_pending(self, thread_id=None, user_id=None):
        seen["user_id"] = user_id
        return []

    monkeypatch.setattr(hitl.ApprovalManager, "get_pending", fake_get_pending)
    secret = get_settings().api.secret_key
    h = {"Authorization": f"Bearer {secret}", "X-User-Id": "carla"}
    assert client.get("/approvals/pending", headers=h).status_code == 200
    assert seen["user_id"] == "carla"
