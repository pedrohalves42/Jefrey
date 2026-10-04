"""Sessao 3: conexao do Google com um botao (state/PKCE, tokens protegidos, sem vazamento)."""
import json
import time
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from src.jefrey.core import google_oauth as G


@pytest.fixture(autouse=True)
def _limpa(monkeypatch, tmp_path):
    G._pending.clear()
    monkeypatch.delenv("JEFREY_OAUTH__CLIENT_ID", raising=False)
    monkeypatch.delenv("JEFREY_OAUTH__CLIENT_SECRET", raising=False)
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path / "cfg"))
    from src.jefrey.core.db import create_oauth2_tables
    create_oauth2_tables()
    yield
    G._pending.clear()


def _config(monkeypatch):
    monkeypatch.setenv("JEFREY_OAUTH__CLIENT_ID", "cid.apps.googleusercontent.com")
    monkeypatch.setenv("JEFREY_OAUTH__CLIENT_SECRET", "segredo-de-teste")


# ---------------- credenciais ----------------
def test_sem_credenciais_nao_esta_configurado():
    assert G.credentials() is None
    with pytest.raises(LookupError):
        G.begin("ana", ["calendar"], "http://localhost:8000/cb")


def test_credenciais_do_ambiente(monkeypatch):
    _config(monkeypatch)
    assert G.credentials() == {"client_id": "cid.apps.googleusercontent.com", "client_secret": "segredo-de-teste"}


def test_credenciais_do_arquivo_baixado_do_google(monkeypatch, tmp_path):
    d = tmp_path / "cfg"
    d.mkdir()
    (d / "google_oauth.json").write_text(json.dumps({"installed": {"client_id": "a", "client_secret": "b"}}), encoding="utf-8")
    assert G.credentials() == {"client_id": "a", "client_secret": "b"}
    (d / "google_oauth.json").write_text("isto nao e json", encoding="utf-8")
    assert G.credentials() is None


# ---------------- inicio, state e PKCE ----------------
def test_endereco_de_autorizacao_tem_pkce_state_e_escopos(monkeypatch):
    _config(monkeypatch)
    url = G.begin("ana", ["calendar", "email"], "http://localhost:8000/connections/google/callback")
    u = urlparse(url)
    q = {k: v[0] for k, v in parse_qs(u.query).items()}
    assert u.netloc == "accounts.google.com"
    assert q["code_challenge_method"] == "S256" and q["response_type"] == "code" and q["access_type"] == "offline"
    assert "calendar.events" in q["scope"] and "gmail.modify" in q["scope"] and "drive" not in q["scope"]
    assert G._pending[q["state"]]["user"] == "ana"
    assert "verifier" not in url and G._pending[q["state"]]["verifier"] not in url


def test_servico_invalido_ou_vazio_e_recusado(monkeypatch):
    _config(monkeypatch)
    for ruim in ([], ["banco"], ["calendar", "root"]):
        with pytest.raises(ValueError):
            G.begin("ana", ruim, "http://localhost:8000/cb")


def test_state_e_de_uso_unico_e_expira(monkeypatch):
    _config(monkeypatch)
    q = parse_qs(urlparse(G.begin("ana", ["calendar"], "http://x/cb")).query)
    st = q["state"][0]
    assert G.consume_state(st)["user"] == "ana"
    assert G.consume_state(st) is None and G.consume_state("") is None and G.consume_state("inventado") is None
    st2 = parse_qs(urlparse(G.begin("ana", ["calendar"], "http://x/cb")).query)["state"][0]
    G._pending[st2]["exp"] = time.time() - 1
    assert G.consume_state(st2) is None


def test_limite_de_pedidos_pendentes(monkeypatch):
    _config(monkeypatch)
    for _ in range(G.MAX_PENDING + 10):
        G.begin("ana", ["calendar"], "http://x/cb")
    assert len(G._pending) <= G.MAX_PENDING


# ---------------- gravar, listar, apagar ----------------
def test_tokens_gravados_protegidos_e_status_sem_segredo():
    from src.jefrey.core.db import get_db
    from src.jefrey.core.models import OAuthToken
    from src.jefrey.core.secret_store import unprotect

    uid = "ana-store"
    saved = G.save_tokens(uid, ["calendar", "email"], {"access_token": "AT-1", "refresh_token": "RT-1", "expires_in": 3600,
                                                       "scope": "openid email"}, "ana@exemplo.com")
    assert sorted(saved) == ["gmail", "google_calendar"]
    with get_db() as s:
        rows = {r.provider: r for r in s.query(OAuthToken).filter(OAuthToken.user_id == uid).all()}
    assert unprotect(rows["gmail"].access_token) == "AT-1" and unprotect(rows["gmail"].refresh_token) == "RT-1"
    st = G.status(uid)
    assert st["connected"] and st["email"] == "ana@exemplo.com" and sorted(st["services"]) == ["calendar", "email"]
    assert "AT-1" not in json.dumps(st) and "RT-1" not in json.dumps(st)
    # reconectar nao duplica
    G.save_tokens(uid, ["calendar"], {"access_token": "AT-2"}, "ana@exemplo.com")
    with get_db() as s:
        assert s.query(OAuthToken).filter(OAuthToken.user_id == uid, OAuthToken.provider == "google_calendar").count() == 1
    revogar = G.delete_tokens(uid)
    assert "RT-1" in revogar
    assert G.status(uid)["connected"] is False
    assert G.status("outra-pessoa")["connected"] is False


# ---------------- API ----------------
@pytest.fixture()
def api():
    from src.jefrey.api import auth_middleware
    from src.jefrey.api.main import app
    auth_middleware._rl_buckets.clear()
    c = TestClient(app, follow_redirects=False)
    tok = c.post("/auth/dev-token", json={"user_id": "apigoogle"}).json()["access_token"]
    return c, {"Authorization": f"Bearer {tok}"}


def test_api_exige_login_e_avisa_quando_nao_configurado(api):
    c, h = api
    assert c.get("/connections/google").status_code == 401
    assert c.post("/connections/google/start", json={"services": ["calendar"]}).status_code == 401
    assert c.delete("/connections/google").status_code == 401
    r = c.post("/connections/google/start", headers=h, json={"services": ["calendar"]})
    assert r.status_code == 409 and "Google" in r.json()["detail"]
    assert c.get("/connections/google", headers=h).json()["configured"] is False


def test_api_fluxo_completo_com_google_simulado(api, monkeypatch):
    import src.jefrey.api.google_connect as gc
    _config(monkeypatch)
    c, h = api
    r = c.post("/connections/google/start", headers=h, json={"services": ["calendar", "email"]})
    assert r.status_code == 200
    url = r.json()["auth_url"]
    q = parse_qs(urlparse(url).query)
    assert q["redirect_uri"][0].endswith("/connections/google/callback")
    state = q["state"][0]

    class Resp:
        def __init__(self, data, status=200):
            self._d, self.status_code = data, status

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError("http")

        def json(self):
            return self._d

    visto = {}

    class Fake:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, data=None, **k):
            visto["data"] = data
            return Resp({"access_token": "AT-api", "refresh_token": "RT-api", "expires_in": 3600, "scope": "openid"})

        async def get(self, url, **k):
            return Resp({"email": "pessoa@exemplo.com"})

    monkeypatch.setattr(gc.httpx, "AsyncClient", Fake)
    # o callback e uma navegacao do navegador: sem cabecalho de login
    r = c.get("/connections/google/callback", params={"code": "codigo", "state": state})
    assert r.status_code == 303 and r.headers["location"] == "/conexoes?google=ok"  # "testserver" nao e endereco local: volta relativo
    assert visto["data"]["code_verifier"] and visto["data"]["client_secret"] == "segredo-de-teste"
    st = c.get("/connections/google", headers=h).json()
    assert st["connected"] and st["email"] == "pessoa@exemplo.com" and sorted(st["services"]) == ["calendar", "email"]
    assert "AT-api" not in json.dumps(st)
    # o mesmo state nao serve duas vezes
    r2 = c.get("/connections/google/callback", params={"code": "codigo", "state": state})
    assert r2.headers["location"] == "/conexoes?google=erro"  # state ja usado: sem origem conhecida, volta relativo
    assert c.delete("/connections/google", headers=h).json() == {"ok": True}
    assert c.get("/connections/google", headers=h).json()["connected"] is False


def test_callback_recusa_state_falso_ou_erro_do_google():
    from src.jefrey.api import auth_middleware
    from src.jefrey.api.main import app
    auth_middleware._rl_buckets.clear()
    c = TestClient(app, follow_redirects=False)
    for params in ({"code": "x", "state": "falso"}, {"error": "access_denied", "state": "falso"}, {}):
        r = c.get("/connections/google/callback", params=params)
        assert r.status_code == 303 and r.headers["location"] == "/conexoes?google=erro"


def test_endereco_de_retorno_usa_o_registrado_na_mesma_porta(monkeypatch):
    monkeypatch.setenv("JEFREY_OAUTH__REDIRECT_URIS", "http://localhost:8000/auth/google/callback")
    assert G.redirect_uri("http://127.0.0.1:8000") == "http://localhost:8000/auth/google/callback"
    assert G.redirect_uri("http://127.0.0.1:8001") == "http://127.0.0.1:8001/connections/google/callback"  # outra porta: padrao
    monkeypatch.setenv("JEFREY_OAUTH__REDIRECT_URIS", "https://evil.example/auth/google/callback,http://localhost:8000/outra/rota")
    assert G.redirect_uri("http://127.0.0.1:8000") == "http://127.0.0.1:8000/connections/google/callback"  # so enderecos locais e conhecidos
    monkeypatch.delenv("JEFREY_OAUTH__REDIRECT_URIS")
    assert G.redirect_uri("http://127.0.0.1:8000") == "http://127.0.0.1:8000/connections/google/callback"


def test_retorno_pelo_endereco_antigo_conclui_o_fluxo_novo_e_volta_a_tela_de_origem(api, monkeypatch):
    """O app do Google so tem registrado /auth/google/callback em localhost: o botao novo funciona sem mexer no Google Cloud,
    e a pessoa volta para http://127.0.0.1 (onde esta o login dela), nao para localhost."""
    import src.jefrey.api.google_connect as gc
    _config(monkeypatch)
    c, h = api
    url = G.begin("apigoogle", ["calendar"], "http://localhost:8000/auth/google/callback", "http://127.0.0.1:8000")
    state = parse_qs(urlparse(url).query)["state"][0]

    class Resp:
        def __init__(self, d):
            self.d, self.status_code = d, 200

        def raise_for_status(self):
            pass

        def json(self):
            return self.d

    class Fake:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, data=None, **k):
            assert data["redirect_uri"] == "http://localhost:8000/auth/google/callback"  # o MESMO endereco usado na ida
            return Resp({"access_token": "AT", "refresh_token": "RT", "expires_in": 3600, "scope": "openid"})

        async def get(self, url, **k):
            return Resp({"email": "pessoa@exemplo.com"})

    monkeypatch.setattr(gc.httpx, "AsyncClient", Fake)
    r = c.get("/auth/google/callback", params={"code": "x", "state": state})
    assert r.status_code == 303 and r.headers["location"] == "http://127.0.0.1:8000/conexoes?google=ok"
    assert c.get("/connections/google", headers=h).json()["connected"] is True
    again = c.get("/auth/google/callback", params={"code": "x", "state": state})  # state de uso unico: cai no fluxo antigo, que o recusa
    assert again.status_code != 303


def test_origem_de_retorno_so_aceita_enderecos_locais():
    import src.jefrey.api.google_connect as gc
    assert gc._back({"return_to": "http://127.0.0.1:8000"}, "ok").headers["location"] == "http://127.0.0.1:8000/conexoes?google=ok"
    assert gc._back({"return_to": "https://evil.example"}, "ok").headers["location"] == "/conexoes?google=ok"
    assert gc._back({"return_to": "http://evil.example"}, "erro").headers["location"] == "/conexoes?google=erro"
    assert gc._back(None, "erro").headers["location"] == "/conexoes?google=erro"


def test_skills_leem_token_protegido(monkeypatch):
    """A skill de agenda abre o token gravado por este fluxo (antes lia texto puro e falhava)."""
    _config(monkeypatch)
    G.save_tokens("ana-skill", ["calendar"], {"access_token": "AT-skill", "refresh_token": "RT-skill"}, None)
    pytest.importorskip("google.oauth2.credentials")
    from src.jefrey.skills import calendar as cal
    creds = cal.CalendarSkill()._get_credentials_for_user("ana-skill")
    assert creds is not None and creds.token == "AT-skill" and creds.client_id == "cid.apps.googleusercontent.com"
