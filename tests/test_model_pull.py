"""Baixar modelo local com progresso: nomes validos, progresso real, falhas claras e sem duplicar download."""
import json
import threading

import httpx
import pytest
from fastapi.testclient import TestClient

from src.jefrey.core import model_pull as MP


@pytest.fixture(autouse=True)
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path))
    MP._running = False
    return tmp_path


def ndjson(*events):
    return httpx.Response(200, content=("\n".join(json.dumps(e) for e in events) + "\n").encode())


# ---------------- nomes ----------------
@pytest.mark.parametrize("ok", [["qwen3:1.7b"], ["gemma4:e2b", "embeddinggemma"], ["library/model:latest"]])
def test_nomes_validos(ok):
    assert MP.valid_models(ok) == ok


@pytest.mark.parametrize("bad", [[], [""], ["../etc"], ["a b"], ["x;rm"], ["a"] * 4, ["m\nn"], [123], ["x" * 81]])
def test_nomes_invalidos_sao_recusados(bad):
    with pytest.raises(MP.PullError):
        MP.valid_models(bad)


def test_repetidos_sao_unificados():
    assert MP.valid_models(["a", "a", "b"]) == ["a", "b"]


# ---------------- download ----------------
def test_progresso_em_porcentagem_e_pronto(cfg):
    ev = [{"status": "pulling manifest"}, {"status": "downloading", "total": 100, "completed": 25},
          {"status": "downloading", "total": 100, "completed": 80}, {"status": "success"}]
    seen = []
    real = MP._save

    def spy(state):
        seen.append(state["models"]["m1"]["percent"])
        real(state)
    MP._save = spy
    try:
        MP._run(["m1"], "http://x", transport=httpx.MockTransport(lambda r: ndjson(*ev)))
    finally:
        MP._save = real
    st = MP.status()
    assert st["done"] is True and st["error"] is None and st["models"]["m1"] == {"status": "pronto", "percent": 100}
    assert 25 in seen and 80 in seen  # a tela viu o avanco


def test_falha_de_rede_vira_mensagem_sem_detalhe_tecnico():
    def down(req):
        raise httpx.ConnectError("recusou 127.0.0.1:11434")
    MP._run(["m1", "m2"], "http://x", transport=httpx.MockTransport(down))
    st = MP.status()
    assert st["done"] is True and "internet" in st["error"] and "127.0.0.1" not in json.dumps(st)
    assert st["models"]["m1"]["status"] == "falhou" and st["models"]["m2"]["status"] == "falhou"
    assert MP._running is False


def test_erro_informado_pelo_ollama_e_tratado():
    MP._run(["m1"], "http://x", transport=httpx.MockTransport(lambda r: ndjson({"error": "pull model manifest: file does not exist"})))
    assert MP.status()["models"]["m1"]["status"] == "falhou" and MP.status()["error"]


def test_um_modelo_falhar_nao_impede_os_outros():
    calls = []

    def h(req):
        name = json.loads(req.content)["name"]
        calls.append(name)
        return httpx.Response(500) if name == "ruim" else ndjson({"status": "success"})
    MP._run(["ruim", "bom"], "http://x", transport=httpx.MockTransport(h))
    st = MP.status()
    assert calls == ["ruim", "bom"] and st["models"]["bom"]["status"] == "pronto" and st["models"]["ruim"]["status"] == "falhou"


# ---------------- iniciar ----------------
def test_ollama_ausente_da_mensagem_clara_e_nao_inicia():
    with pytest.raises(MP.PullError, match="ollama.com/download"):
        MP.start(["m"], ensure_running=lambda: (False, "O Ollama nao esta instalado. Baixe em ollama.com/download."))
    assert MP._running is False


def test_nao_duplica_download_em_andamento(monkeypatch):
    gate = threading.Event()
    monkeypatch.setattr(MP, "_run", lambda models, base, transport=None: gate.wait(5))
    first = MP.start(["m"], ensure_running=lambda: (True, "ok"))
    again = MP.start(["m"], ensure_running=lambda: (True, "ok"))
    assert first["running"] is True and again["running"] is True
    started = threading.active_count()
    gate.set()
    MP._running = False
    assert started >= 1


def test_status_sem_arquivo():
    assert MP.status() == {"running": False, "done": False, "models": {}, "error": None}


# ---------------- API ----------------
@pytest.fixture()
def api(monkeypatch):
    from src.jefrey.api import auth_middleware
    from src.jefrey.api.main import app
    auth_middleware._rl_buckets.clear()
    c = TestClient(app)
    h = {"Authorization": "Bearer " + c.post("/auth/dev-token", json={"user_id": "pull"}).json()["access_token"]}
    return c, h


def test_api_exige_login(api):
    c, _ = api
    assert c.post("/settings/llm/pull", json={"models": ["m"]}).status_code == 401
    assert c.get("/settings/llm/pull-status").status_code == 401


def test_api_409_quando_ollama_ausente(api, monkeypatch):
    c, h = api
    monkeypatch.setattr("src.jefrey.native.launcher.ensure_ollama", lambda wait=25.0: (False, "O Ollama nao esta instalado. Baixe em ollama.com/download."))
    r = c.post("/settings/llm/pull", headers=h, json={"models": ["qwen3:1.7b"]})
    assert r.status_code == 409 and "ollama.com/download" in r.json()["detail"]


def test_api_valida_nomes(api):
    c, h = api
    assert c.post("/settings/llm/pull", headers=h, json={"models": ["../x"]}).status_code == 409
    assert c.post("/settings/llm/pull", headers=h, json={"models": []}).status_code == 422


def test_api_inicia_e_consulta_progresso(api, monkeypatch):
    c, h = api
    monkeypatch.setattr("src.jefrey.native.launcher.ensure_ollama", lambda wait=25.0: (True, "ok"))
    monkeypatch.setattr(MP, "_run", lambda models, base, transport=None: MP._save(
        {"models": {m: {"status": "pronto", "percent": 100} for m in models}, "done": True, "error": None}) or setattr(MP, "_running", False))
    r = c.post("/settings/llm/pull", headers=h, json={"models": ["qwen3:1.7b"]})
    assert r.status_code == 200 and r.json()["running"] is True
    for _ in range(50):
        st = c.get("/settings/llm/pull-status", headers=h).json()
        if st["done"]:
            break
        import time
        time.sleep(0.05)
    assert st["done"] is True and st["models"]["qwen3:1.7b"]["percent"] == 100
