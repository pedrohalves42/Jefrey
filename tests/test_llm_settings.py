"""/settings/llm: escolha de modelo local ou nuvem, sem vazar a chave."""
import json

import pytest
from fastapi.testclient import TestClient

from src.jefrey.api.main import app
from src.jefrey.core import llm_provider as lp


@pytest.fixture()
def cfgdir(tmp_path, monkeypatch):
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture()
def client():
    return TestClient(app)


def _auth(client):
    r = client.post("/auth/dev-token")
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_exige_autenticacao(client, cfgdir):
    assert client.get("/settings/llm").status_code == 401


def test_padrao_local_sem_chave(client, cfgdir):
    r = client.get("/settings/llm", headers=_auth(client))
    assert r.status_code == 200
    assert r.json()["has_key"] is False and r.json()["provider"] == "ollama"


def test_trocar_para_claude_exige_chave(client, cfgdir):
    h = _auth(client)
    r = client.put("/settings/llm", headers=h, json={"provider": "anthropic", "model": "claude-sonnet-4-5"})
    assert r.status_code == 422


def test_salvar_claude_com_chave_nao_devolve_a_chave(client, cfgdir):
    h = _auth(client)
    r = client.put("/settings/llm", headers=h, json={
        "provider": "anthropic", "model": "claude-sonnet-4-5", "api_key": "sk-ant-segredo123"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "anthropic" and body["has_key"] is True
    assert "segredo123" not in json.dumps(body)
    assert "segredo123" not in (cfgdir / "llm.runtime.json").read_text(encoding="utf-8")
    assert lp.config_from_settings().api_key == "sk-ant-segredo123"
    assert "segredo123" not in client.get("/settings/llm", headers=h).text


def test_manter_chave_quando_api_key_ausente_e_apagar_com_vazio(client, cfgdir):
    h = _auth(client)
    client.put("/settings/llm", headers=h, json={"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-x"})
    client.put("/settings/llm", headers=h, json={"provider": "openai", "model": "gpt-4o"})
    assert lp.load_saved_key() == "sk-x"
    r = client.put("/settings/llm", headers=h, json={"provider": "ollama", "model": "qwen2.5:3b", "api_key": ""})
    assert r.status_code == 200 and r.json()["has_key"] is False


def test_provedor_invalido(client, cfgdir):
    r = client.put("/settings/llm", headers=_auth(client), json={"provider": "xyz", "model": "m"})
    assert r.status_code == 422


def test_presets(client, cfgdir):
    ids = {p["id"] for p in client.get("/settings/llm/presets", headers=_auth(client)).json()["presets"]}
    assert {"ollama-local", "anthropic", "openai"} <= ids


def test_salvamento_rejeitado_nao_altera_a_configuracao(client, cfgdir):
    """Regressao: antes gravava o arquivo e so depois validava, deixando o chat preso."""
    h = _auth(client)
    antes = client.get("/settings/llm", headers=h).json()
    r = client.put("/settings/llm", headers=h, json={"provider": "anthropic", "model": "claude-sonnet-4-5"})
    assert r.status_code == 422
    assert "chave" in r.json()["detail"].lower() and "JEFREY_LLM" not in r.json()["detail"]
    assert not (cfgdir / "llm.runtime.json").exists()
    assert client.get("/settings/llm", headers=h).json() == antes
