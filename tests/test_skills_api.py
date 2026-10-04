"""/skills lista o que esta realmente carregado (nada inventado)."""
import pytest
from fastapi.testclient import TestClient

from src.jefrey.api.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _h(client):
    return {"Authorization": f"Bearer {client.post('/auth/dev-token').json()['access_token']}"}


def test_exige_login(client):
    assert client.get("/skills").status_code == 401


def test_lista_skills_e_ferramentas_reais(client):
    r = client.get("/skills", headers=_h(client))
    assert r.status_code == 200
    j = r.json()
    names = {s["name"] for s in j["skills"]}
    assert {"notes", "web_search"} <= names
    assert j["count"] == len(j["skills"]) and j["tool_count"] == sum(len(s["tools"]) for s in j["skills"])
    notes = next(s for s in j["skills"] if s["name"] == "notes")
    assert "save_note" in {t["name"] for t in notes["tools"]}


def test_nenhum_numero_fixo_a_mais(client):
    j = client.get("/skills", headers=_h(client)).json()
    assert j["count"] == len(j["skills"])
