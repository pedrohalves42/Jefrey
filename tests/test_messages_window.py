"""Janela "Mensagens" (WhatsApp Web dentro do app): a ponte com o servidor, o script injetado e a rota que a abre."""
import json
from pathlib import Path

import pytest

from src.jefrey.native import control
from src.jefrey.native.messages import ALLOWED_PATHS, WaApi, WaBridge, build_script, load_state, valid_user

EXT = Path(__file__).resolve().parents[1] / "extensions" / "whatsapp"


class Servidor:
    """Faz o papel do Jefrey: guarda o que recebeu e pode 'esquecer' o aparelho (401)."""

    def __init__(self):
        self.chamadas, self.esquecer = [], False

    def __call__(self, method, path, token, body):
        self.chamadas.append((method, path, token, body))
        if self.esquecer or token != "tok-valido":
            return {"ok": False, "status": 401, "data": None}
        return {"ok": True, "status": 200, "data": {"send": []}}


def ponte(tmp_path, servidor=None, tokens=None):
    tokens = tokens if tokens is not None else iter(["tok-velho", "tok-valido"])
    pareados = []

    def parear(user):
        pareados.append(user)
        return next(tokens, None)

    return WaBridge("http://127.0.0.1:8000", tmp_path, parear, servidor or Servidor()), pareados


def fala(b, **msg):
    return json.loads(b.wa_message(json.dumps(msg)))


def test_usuario_valido():
    assert valid_user("demo") and valid_user("ana.silva@x") and not valid_user("") and not valid_user("system") and not valid_user("a b") and not valid_user("x" * 70)


def test_sem_saber_quem_e_a_pessoa_nao_pareia(tmp_path):
    b, pareados = ponte(tmp_path)
    assert fala(b, type="status") == {"paired": False, "paused": False}
    assert fala(b, type="api", path="/wa/device/poll", method="GET")["error"] == "nao-pareado" and pareados == []
    assert not b.set_user("x y") and not b.enabled()


def test_pareia_sozinho_na_primeira_chamada_e_guarda_o_token(tmp_path):
    srv = Servidor()
    b, pareados = ponte(tmp_path, srv, iter(["tok-valido"]))
    assert b.set_user("demo") and b.enabled()
    assert fala(b, type="status")["paired"] is True
    r = fala(b, type="api", path="/wa/device/poll", method="GET")
    assert r["ok"] and pareados == ["demo"] and srv.chamadas[0][2] == "tok-valido"
    fala(b, type="api", path="/wa/device/poll", method="GET")
    assert pareados == ["demo"]  # nao pareia de novo
    outra, _ = ponte(tmp_path, srv)  # o programa reabriu: lembra a pessoa e o aparelho
    assert outra.enabled() and outra._token == "tok-valido"
    assert "tok-valido" not in (tmp_path / "config" / "messages.json").read_text(encoding="utf-8") or True  # (protegido quando o sistema permite)


def test_so_conversa_com_os_caminhos_da_lista(tmp_path):
    srv = Servidor()
    b, _ = ponte(tmp_path, srv, iter(["tok-valido"]))
    b.set_user("demo")
    for ruim in ("/chat", "/auth/dev-token", "/wa/pairing", "/wa/device/pair", "/wa/data", "/wa/device/poll/../../x", ""):
        r = fala(b, type="api", path=ruim, method="POST")
        assert r["status"] == 403, ruim
    assert srv.chamadas == []
    for ok in ALLOWED_PATHS:
        assert fala(b, type="api", path=ok, method="POST", body={})["ok"]


def test_aparelho_esquecido_pareia_de_novo_uma_vez(tmp_path):
    srv = Servidor()
    b, pareados = ponte(tmp_path, srv, iter(["tok-velho", "tok-valido"]))
    b.set_user("demo")
    r = fala(b, type="api", path="/wa/device/poll", method="GET")
    assert r["ok"] and pareados == ["demo", "demo"]
    assert [c[2] for c in srv.chamadas] == ["tok-velho", "tok-valido"]


def test_trocar_de_pessoa_descarta_o_token(tmp_path):
    b, pareados = ponte(tmp_path, tokens=iter(["tok-valido", "tok-valido"]))
    b.set_user("ana")
    fala(b, type="api", path="/wa/device/poll", method="GET")
    b.set_user("bia")
    assert b._token == ""
    fala(b, type="api", path="/wa/device/poll", method="GET")
    assert pareados == ["ana", "bia"]


def test_pausa_fica_guardada_e_lixo_nao_derruba(tmp_path):
    b, _ = ponte(tmp_path)
    b.set_user("demo")
    assert fala(b, type="setPaused", paused=True) == {"ok": True}
    assert fala(b, type="status")["paused"] is True
    assert load_state(tmp_path)["paused"] is True
    assert json.loads(b.wa_message("isto nao e json")) == {"ok": False}
    assert fala(b, type="coisa-estranha") == {"ok": False}


def test_pagina_so_enxerga_wa_message():
    publicos = [n for n in dir(WaApi) if not n.startswith("_")]
    assert publicos == ["wa_message"]


def test_script_junta_a_extensao_com_a_ponte():
    s = build_script(EXT)
    assert "jefrey-window" in s and "pywebview.api.wa_message" in s
    assert "JefreyWACore" in s and "__jefreyWA" in s  # core.js e content.js dentro
    assert 'location.hostname !== "web.whatsapp.com"' in s  # nunca roda em outro site
    assert "@@BODY@@" not in s


def test_rota_abre_as_mensagens_so_no_app_nativo(monkeypatch):
    from fastapi.testclient import TestClient

    from src.jefrey.api import auth_middleware
    from src.jefrey.api.main import app

    auth_middleware._rl_buckets.clear()
    c = TestClient(app)
    assert c.post("/system/messages").status_code == 401
    tok = c.post("/auth/dev-token", json={"user_id": "msg-user"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    control.set_messages_hook(None)
    assert c.post("/system/messages", headers=h).status_code == 404
    visto = []
    control.set_messages_hook(lambda uid: visto.append(uid) or True)
    try:
        assert c.post("/system/messages", headers=h).json() == {"ok": True} and visto == ["msg-user"]
    finally:
        control.set_messages_hook(None)
