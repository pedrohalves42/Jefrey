"""Protecao do modo local: Host falso (DNS rebinding), outro site (CSRF) e WebSocket sao recusados."""
import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.jefrey.api.local_guard import LocalGuardMiddleware, _hostname

PORT = 8000


def make(**kw):
    app = FastAPI()

    @app.get("/ler")
    async def ler():
        return {"ok": True}

    @app.post("/escrever")
    async def escrever():
        return {"ok": True}

    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        await sock.accept()
        await sock.send_text("oi")
        await sock.close()

    app.add_middleware(LocalGuardMiddleware, port=PORT, **kw)
    return TestClient(app, base_url=f"http://127.0.0.1:{PORT}")


@pytest.fixture()
def c():
    return make()


# ---------------- Host (DNS rebinding) ----------------
@pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost:8000", "LOCALHOST:8000", "[::1]:8000", "127.0.0.1", "localhost"])
def test_hosts_locais_passam(c, host):
    assert c.get("/ler", headers={"Host": host}).status_code == 200


@pytest.mark.parametrize("host", ["evil.example", "evil.example:8000", "127.0.0.1.evil.example", "localhost.evil.com:8000",
                                  "192.168.0.10:8000", "0.0.0.0:8000", "", "127.0.0.1@evil.example"])
def test_host_estranho_e_recusado_ate_em_leitura(c, host):
    assert c.get("/ler", headers={"Host": host}).status_code == 400


def test_host_extra_configurado_pelo_usuario():
    c2 = make(extra_hosts=["jefrey.local"])
    assert c2.get("/ler", headers={"Host": "jefrey.local:8000"}).status_code == 200
    assert c2.get("/ler", headers={"Host": "outro.local"}).status_code == 400


# ---------------- Origin / CSRF ----------------
def test_escrita_sem_origin_passa_cliente_que_nao_e_navegador(c):
    assert c.post("/escrever").status_code == 200  # curl, testes, o proprio app no servidor


@pytest.mark.parametrize("origin", ["http://127.0.0.1:8000", "http://localhost:8000", "http://[::1]:8000"])
def test_escrita_da_propria_tela_passa(c, origin):
    assert c.post("/escrever", headers={"Origin": origin, "Sec-Fetch-Site": "same-origin"}).status_code == 200


@pytest.mark.parametrize("origin", ["http://evil.example", "https://evil.example", "null", "http://localhost:9999",
                                    "http://localhost", "http://127.0.0.1:8001", "https://127.0.0.1:8000.evil.com", "file://"])
def test_escrita_vinda_de_outro_site_ou_outra_porta_e_recusada(c, origin):
    assert c.post("/escrever", headers={"Origin": origin}).status_code == 403


@pytest.mark.parametrize("site", ["cross-site", "same-site"])
def test_sec_fetch_site_de_fora_e_recusado_em_escrita(c, site):
    assert c.post("/escrever", headers={"Sec-Fetch-Site": site}).status_code == 403


def test_sec_fetch_site_none_e_digitado_na_barra_ou_atalho(c):
    assert c.post("/escrever", headers={"Sec-Fetch-Site": "none"}).status_code == 200


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_todos_os_metodos_de_escrita_sao_protegidos(c, method):
    assert c.request(method, "/escrever", headers={"Origin": "http://evil.example"}).status_code in (403, 405)


def test_leitura_de_outra_origem_nao_e_bloqueada_aqui(c):
    # leitura entre sites ja e impedida pelo CORS (fechado por padrao); o guarda foca em Host e escrita
    assert c.get("/ler", headers={"Origin": "http://evil.example"}).status_code == 200


def test_origin_extra_configurado_pelo_usuario():
    c2 = make(extra_origins=["http://localhost:5173"])
    assert c2.post("/escrever", headers={"Origin": "http://localhost:5173"}).status_code == 200
    assert c2.post("/escrever", headers={"Origin": "http://localhost:5174"}).status_code == 403


# ---------------- WebSocket ----------------
def test_websocket_da_propria_tela_conecta(c):
    with c.websocket_connect("/ws", headers={"Host": f"127.0.0.1:{PORT}", "Origin": f"http://127.0.0.1:{PORT}"}) as ws:
        assert ws.receive_text() == "oi"


def test_websocket_de_outro_site_e_recusado(c):
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/ws", headers={"Host": f"127.0.0.1:{PORT}", "Origin": "http://evil.example"}):
            pass


def test_websocket_com_host_falso_e_recusado(c):
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/ws", headers={"Host": "evil.example"}):
            pass


# ---------------- auxiliares ----------------
@pytest.mark.parametrize("v,esperado", [("LocalHost:8000", "localhost"), ("[::1]:8000", "[::1]"), ("127.0.0.1", "127.0.0.1"),
                                        ("", ""), ("[::1]", "[::1]")])
def test_hostname(v, esperado):
    assert _hostname(v) == esperado


def test_ativacao_pelo_modo(monkeypatch):
    from src.jefrey.api.local_guard import local_guard_enabled
    monkeypatch.delenv("JEFREY_MODE", raising=False)
    monkeypatch.delenv("JEFREY_LOCAL_GUARD", raising=False)
    monkeypatch.setenv("JEFREY_ENV", "prod")
    assert not local_guard_enabled()  # producao real: nao se aplica
    monkeypatch.setenv("JEFREY_ENV", "dev")
    assert local_guard_enabled()  # dev (Docker ou nao): o login /auth/dev-token existe, entao protege
    monkeypatch.setenv("JEFREY_LOCAL_GUARD", "0")
    assert not local_guard_enabled()
    monkeypatch.delenv("JEFREY_LOCAL_GUARD")
    monkeypatch.setenv("JEFREY_ENV", "prod")
    monkeypatch.setenv("JEFREY_MODE", "native")
    assert local_guard_enabled()
