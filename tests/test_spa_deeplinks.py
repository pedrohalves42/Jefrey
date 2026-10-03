"""Recarregar uma pagina do app (ex.: /settings) serve o app; a API continua protegida."""
import pytest
from fastapi.testclient import TestClient

from src.jefrey.api.main import app

HTML = {"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.mark.parametrize("path", ["/settings", "/memory", "/approvals", "/observability", "/knowledge", "/studio"])
def test_navegacao_de_navegador_serve_o_app(client, path):
    r = client.get(path, headers=HTML)
    assert r.status_code == 200 and "<div id=\"root\"" in r.text


@pytest.mark.parametrize("path", ["/memory", "/approvals/pending", "/settings/llm", "/memory/search?q=x"])
def test_chamada_de_api_sem_token_continua_401(client, path):
    assert client.get(path, headers={"Accept": "application/json"}).status_code == 401


def test_api_nao_e_exposta_so_por_mandar_accept_html(client):
    assert client.get("/memory/search?q=x", headers=HTML).status_code == 401
    assert client.get("/settings/llm", headers=HTML).status_code == 401
