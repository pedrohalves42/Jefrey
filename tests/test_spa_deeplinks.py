"""Recarregar uma pagina do app (ex.: /settings) serve o app; a API continua protegida."""
import pytest
from fastapi.testclient import TestClient

from src.jefrey.api.main import app

HTML = {"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.mark.parametrize("path", ["/settings", "/memory", "/approvals", "/observability", "/knowledge", "/studio",
                                  "/memoria", "/skills", "/configuracoes", "/avancado"])
def test_navegacao_de_navegador_serve_o_app(client, path):
    r = client.get(path, headers=HTML)
    assert r.status_code == 200 and "<div id=\"root\"" in r.text


@pytest.mark.parametrize("path", ["/memory", "/approvals/pending", "/settings/llm", "/memory/search?q=x"])
def test_chamada_de_api_sem_token_continua_401(client, path):
    assert client.get(path, headers={"Accept": "application/json"}).status_code == 401


def test_api_nao_e_exposta_so_por_mandar_accept_html(client):
    assert client.get("/memory/search?q=x", headers=HTML).status_code == 401
    assert client.get("/settings/llm", headers=HTML).status_code == 401


@pytest.mark.parametrize("path,tipo", [
    ("/manifest.json", "json"), ("/sw.js", "javascript"), ("/images/icon-192.png", "image/png"),
    ("/images/icon-512.png", "image/png"), ("/images/icon-maskable-512.png", "image/png"),
])
def test_arquivos_para_instalar_o_app_sao_publicos(client, path, tipo):
    """O navegador busca manifesto, service worker e icones sem login: precisam abrir."""
    r = client.get(path)
    assert r.status_code == 200 and tipo in r.headers["content-type"], (path, r.status_code)


def test_publicar_imagens_nao_abre_a_api(client):
    assert client.get("/images/../memory/recent").status_code in (401, 404)
    assert client.get("/memory/recent").status_code == 401
