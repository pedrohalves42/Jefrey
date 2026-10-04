"""Sessao 2B: preparar a audicao (Whisper local) em segundo plano, com estado claro para a tela."""
import time

import pytest
from fastapi.testclient import TestClient

from src.jefrey.core import voice_ready as V


@pytest.fixture(autouse=True)
def _limpa(monkeypatch):
    V._state.update(running=False, error=None)
    monkeypatch.delenv("JEFREY_VOICE__STT__MODEL", raising=False)
    yield
    V._state.update(running=False, error=None)


def _espera(cond, t=3.0):
    fim = time.time() + t
    while time.time() < fim:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_escolhe_o_modelo_pelo_computador(monkeypatch):
    monkeypatch.setattr(V.os, "cpu_count", lambda: 4)
    assert V.pick_model("base") == "base"
    monkeypatch.setattr(V.os, "cpu_count", lambda: 12)
    assert V.pick_model("base") == "small"
    monkeypatch.setenv("JEFREY_VOICE__STT__MODEL", "tiny")  # quem configurou manda
    assert V.pick_model("tiny") == "tiny"


def test_detecta_modelo_ja_baixado(tmp_path, monkeypatch):
    monkeypatch.setattr(V, "_hub_cache", lambda: tmp_path)
    assert V.model_cached("base") is False
    snap = tmp_path / "models--Systran--faster-whisper-base" / "snapshots" / "abc"
    snap.mkdir(parents=True)
    assert V.model_cached("base") is False  # pasta sem o arquivo do modelo
    (snap / "model.bin").write_bytes(b"x")
    assert V.model_cached("base") is True and V.model_cached("small") is False


def test_prepara_em_segundo_plano_e_nao_duplica():
    chamadas = []

    def lento():
        chamadas.append(1)
        time.sleep(0.2)

    assert V.prepare(lento) is True
    assert V.prepare(lento) is False  # ja preparando
    assert V.status()["running"] is True
    assert _espera(lambda: not V.status()["running"])
    assert len(chamadas) == 1 and V.status()["error"] is None


def test_erro_vira_mensagem_humana_sem_detalhe_tecnico():
    def falha():
        raise RuntimeError("HTTPSConnectionPool(host='huggingface.co') caminho C:\\segredo")

    V.prepare(falha)
    assert _espera(lambda: not V.status()["running"])
    err = V.status()["error"]
    assert err == V.FRIENDLY_ERROR and "huggingface" not in err and "C:" not in err
    # depois de um erro da para tentar de novo
    assert V.prepare(lambda: None) is True
    assert _espera(lambda: not V.status()["running"]) and V.status()["error"] is None


def test_pronto_quando_o_modelo_ja_esta_no_computador(monkeypatch):
    monkeypatch.setattr(V, "model_cached", lambda name: True)
    assert V.status()["ready"] is True
    monkeypatch.setattr(V, "model_cached", lambda name: False)
    monkeypatch.setattr(V, "_engine_loaded", lambda: False)
    assert V.status()["ready"] is False
    monkeypatch.setattr(V, "_engine_loaded", lambda: True)
    assert V.status()["ready"] is True


def test_api_exige_login_e_responde_estado(monkeypatch):
    from src.jefrey.api import auth_middleware
    from src.jefrey.api.main import app

    auth_middleware._rl_buckets.clear()
    c = TestClient(app)
    assert c.get("/system/voice").status_code == 401 and c.post("/system/voice/prepare").status_code == 401
    tok = c.post("/auth/dev-token", json={"user_id": "voz"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    monkeypatch.setattr(V, "prepare", lambda loader=None: True)
    monkeypatch.setattr(V, "model_cached", lambda name: False)
    monkeypatch.setattr(V, "_engine_loaded", lambda: False)
    st = c.get("/system/voice", headers=h).json()
    assert st["ready"] is False and set(st) == {"ready", "running", "error", "model"}
    r = c.post("/system/voice/prepare", headers=h).json()
    assert r["started"] is True and "ready" in r
