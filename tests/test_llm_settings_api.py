"""API de configuracao do modelo: assistente de primeira execucao, reservas e login de 1 clique do OpenRouter."""
import base64
import hashlib
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from src.jefrey.api import llm_settings as api
from src.jefrey.api.main import app


@pytest.fixture()
def c(tmp_path, monkeypatch):
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path))
    api._pkce.clear()
    from src.jefrey.api import auth_middleware
    auth_middleware._rl_buckets.clear()  # o limite por usuario (burst 20) e protecao real; cada teste comeca zerado
    return TestClient(app), tmp_path


_USER_TOKENS: dict = {}


def H(client, user="ana"):
    """Um token por usuario para o modulo inteiro: o /auth/dev-token tem limite de pedidos (protecao real)."""
    if user not in _USER_TOKENS:
        _USER_TOKENS[user] = f"Bearer {client.post('/auth/dev-token', json={'user_id': user}).json()['access_token']}"
    return {"Authorization": _USER_TOKENS[user]}


# ---------------- primeira execucao e presets ----------------
def test_sem_escolha_salva_diz_que_nao_esta_configurado(c):
    client, _ = c
    v = client.get("/settings/llm", headers=H(client)).json()
    assert v["configured"] is False and v["fallbacks"] == 0


def test_depois_de_salvar_fica_configurado_e_a_chave_nao_volta(c):
    client, tmp = c
    h = H(client)
    r = client.put("/settings/llm", headers=h, json={"provider": "openai", "model": "openai/gpt-6-luna",
                                                      "base_url": "https://openrouter.ai/api", "api_key": "sk-or-secreto"})
    assert r.status_code == 200 and r.json()["configured"] is True and r.json()["has_key"] is True
    assert "sk-or-secreto" not in r.text and "sk-or-secreto" not in client.get("/settings/llm", headers=h).text
    assert "sk-or-secreto" not in (tmp / "llm.runtime.json").read_text(encoding="utf-8")


def test_nuvem_sem_chave_e_recusada_com_mensagem(c):
    client, _ = c
    r = client.put("/settings/llm", headers=H(client), json={"provider": "anthropic", "model": "claude-sonnet-5-5"})
    assert r.status_code == 422 and "chave" in r.json()["detail"]


def test_presets_comecam_pelo_recomendado_com_modelos_conferidos(c):
    client, _ = c
    p = client.get("/settings/llm/presets", headers=H(client)).json()["presets"]
    assert p[0]["id"] == "openrouter" and p[0]["recommended"] and p[0]["one_click"]
    assert "openai/gpt-6-luna" in p[0]["models"] and "anthropic/claude-sonnet-5.5" in p[0]["models"]
    assert {x["id"] for x in p} >= {"openrouter", "anthropic", "openai", "ollama-local"}


def test_conselho_de_modelo_local_exige_login_e_vem_com_nuvem_como_padrao(c, monkeypatch):
    client, _ = c
    assert client.get("/settings/llm/advice").status_code == 401
    monkeypatch.setattr(api, "detect_gpu", lambda: None)
    a = client.get("/settings/llm/advice", headers=H(client)).json()
    assert a["default"] == "cloud" and a["suggest_local"] is False and a["measured"] is False


def test_conselho_com_placa_capaz(c, monkeypatch):
    from src.jefrey.core.hardware import GpuInfo
    client, _ = c
    monkeypatch.setattr(api, "detect_gpu", lambda: GpuInfo("NVIDIA RTX 4070", 12.0, "nvidia"))
    a = client.get("/settings/llm/advice", headers=H(client)).json()
    assert a["suggest_local"] is True and a["model"] == "gemma4:e4b" and a["gpu"]["name"] == "NVIDIA RTX 4070"


# ---------------- reservas ----------------
def test_reservas_ida_e_volta_sem_vazar_chave(c):
    client, tmp = c
    h = H(client)
    client.put("/settings/llm", headers=h, json={"provider": "ollama", "model": "qwen3:1.7b"})
    body = [{"id": "r1", "provider": "openai", "model": "openai/gpt-6-luna", "base_url": "https://openrouter.ai/api", "api_key": "sk-reserva"}]
    r = client.put("/settings/llm/fallbacks", headers=h, json=body)
    assert r.status_code == 200 and r.json()["fallbacks"][0]["has_key"] is True
    assert "sk-reserva" not in r.text and "sk-reserva" not in client.get("/settings/llm/fallbacks", headers=h).text
    assert client.get("/settings/llm", headers=h).json()["fallbacks"] == 1


def test_reserva_invalida_422(c):
    client, _ = c
    r = client.put("/settings/llm/fallbacks", headers=H(client), json=[{"id": "r1", "provider": "anthropic", "model": "m"}])
    assert r.status_code == 422


def test_reservas_exigem_login(c):
    client, _ = c
    assert client.get("/settings/llm/fallbacks").status_code == 401
    assert client.put("/settings/llm/fallbacks", json=[]).status_code == 401


# ---------------- OpenRouter: 1 clique ----------------
_TOKENS: dict = {}


def start(client):
    h = H(client)
    r = client.post("/settings/llm/openrouter/start", headers=h)
    assert r.status_code == 200
    u = urlparse(r.json()["auth_url"])
    return u, {k: v[0] for k, v in parse_qs(u.query).items()}


def test_start_gera_pkce_s256_e_state_e_callback_local(c):
    client, _ = c
    u, q = start(client)
    assert (u.scheme, u.netloc, u.path) == ("https", "openrouter.ai", "/auth")
    assert q["code_challenge_method"] == "S256" and len(q["state"]) >= 24
    assert q["callback_url"].endswith("/settings/llm/openrouter/callback")
    verifier, _exp = api._pkce[q["state"]]
    assert q["code_challenge"] == base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def test_start_exige_login(c):
    client, _ = c
    assert client.post("/settings/llm/openrouter/start").status_code == 401


def mock_exchange(monkeypatch, handler):
    real = httpx.AsyncClient

    class Fake(real):
        def __init__(self, *a, **kw):
            super().__init__(*a, transport=httpx.MockTransport(handler), **kw)
    monkeypatch.setattr(api.httpx, "AsyncClient", Fake)


def test_callback_troca_o_codigo_e_salva_a_chave_do_usuario(c, monkeypatch):
    client, tmp = c
    _, q = start(client)
    seen = {}

    def h(req):
        import json
        seen.update(json.loads(req.content))
        seen["url"] = str(req.url)
        return httpx.Response(200, json={"key": "sk-or-v1-do-usuario"})
    mock_exchange(monkeypatch, h)
    r = client.get("/settings/llm/openrouter/callback", params={"code": "abc123", "state": q["state"]}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/?conectado=openrouter"
    assert seen["url"] == "https://openrouter.ai/api/v1/auth/keys" and seen["code"] == "abc123"
    assert seen["code_challenge_method"] == "S256" and len(seen["code_verifier"]) >= 40
    cfg = client.get("/settings/llm", headers=H(client)).json()
    assert cfg["provider"] == "openai" and cfg["model"] == "openai/gpt-6-luna" and cfg["has_key"] and cfg["configured"]
    assert "sk-or-v1-do-usuario" not in (tmp / "llm.runtime.json").read_text(encoding="utf-8")


def test_callback_funciona_sem_login_do_jefrey_mas_so_com_state_valido(c, monkeypatch):
    client, _ = c
    mock_exchange(monkeypatch, lambda req: httpx.Response(200, json={"key": "k"}))
    for params in ({"code": "x", "state": "inventado"}, {"code": "x"}, {"state": "s"}, {}):
        r = client.get("/settings/llm/openrouter/callback", params=params, follow_redirects=False)
        assert r.status_code == 303 and "erro=openrouter" in r.headers["location"], params


def test_state_e_de_uso_unico(c, monkeypatch):
    client, _ = c
    _, q = start(client)
    mock_exchange(monkeypatch, lambda req: httpx.Response(200, json={"key": "k"}))
    ok = client.get("/settings/llm/openrouter/callback", params={"code": "x", "state": q["state"]}, follow_redirects=False)
    again = client.get("/settings/llm/openrouter/callback", params={"code": "x", "state": q["state"]}, follow_redirects=False)
    assert "conectado" in ok.headers["location"] and "erro" in again.headers["location"]


def test_state_expirado_e_recusado(c, monkeypatch):
    client, _ = c
    _, q = start(client)
    v, _ = api._pkce[q["state"]]
    api._pkce[q["state"]] = (v, time.time() - 1)
    mock_exchange(monkeypatch, lambda req: httpx.Response(200, json={"key": "k"}))
    r = client.get("/settings/llm/openrouter/callback", params={"code": "x", "state": q["state"]}, follow_redirects=False)
    assert "erro=openrouter" in r.headers["location"]


@pytest.mark.parametrize("resp", [httpx.Response(400), httpx.Response(500), httpx.Response(200, json={}), httpx.Response(200, json={"key": ""})])
def test_falha_na_troca_nao_salva_nada(c, monkeypatch, resp):
    client, _ = c
    _, q = start(client)
    mock_exchange(monkeypatch, lambda req: resp)
    r = client.get("/settings/llm/openrouter/callback", params={"code": "x", "state": q["state"]}, follow_redirects=False)
    assert "erro=openrouter" in r.headers["location"]
    assert client.get("/settings/llm", headers=H(client)).json()["configured"] is False


def test_limite_de_pedidos_pendentes(c, monkeypatch):
    client, _ = c
    monkeypatch.setenv("JEFREY_HTTP_RATE_BURST", "1000")  # aqui queremos testar o limite do PKCE, nao o do HTTP
    monkeypatch.setenv("JEFREY_HTTP_RATE_PER_MIN", "100000")
    for _ in range(30):
        start(client)
    assert len(api._pkce) <= 20
