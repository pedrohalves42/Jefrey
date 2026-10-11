"""Lancador: registros sem segredos, porta alternativa, bandeja tolerante, modelo local so se escolhido, rota de sair."""
import builtins
import logging
import socket
import sys

import pytest
from fastapi.testclient import TestClient

from src.jefrey.native import control, launcher as L


# ---------------- mascara de segredos ----------------
@pytest.mark.parametrize("bruto,sumiu", [
    ("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abcdef.ghijkl", "eyJhbGciOiJIUzI1NiJ9"),
    ("usando chave sk-or-v1-abcdef1234567890", "abcdef1234567890"),
    ("api_key=supersecreta123", "supersecreta123"),
    ('{"password": "minhasenha99"}', "minhasenha99"),
    ("token: abc123def456", "abc123def456"),
])
def test_redact_esconde_segredos(bruto, sumiu):
    out = L.redact(bruto)
    assert sumiu not in out and "***" in out


def test_redact_nao_estraga_texto_comum():
    assert L.redact("Servidor iniciado na porta 8000") == "Servidor iniciado na porta 8000"


def test_registros_em_arquivo_sem_segredos(tmp_path):
    root = logging.getLogger()
    antes = list(root.handlers)
    try:
        path = L.setup_logging(tmp_path / "logs")
        logging.getLogger("teste").info("chamada com Bearer abcdefghijklmnop e sk-or-v1-zzzzzzzzzzzz")
        logging.getLogger("teste").warning("mensagem normal %s", "ok")
        for h in root.handlers:
            h.flush()
        txt = path.read_text(encoding="utf-8")
        assert "abcdefghijklmnop" not in txt and "zzzzzzzzzzzz" not in txt
        assert "mensagem normal ok" in txt and path.name == "jefrey.log"
    finally:
        for h in list(root.handlers):
            if h not in antes:
                root.removeHandler(h)
                h.close()


# ---------------- porta ----------------
def test_porta_ocupada_vira_a_proxima_livre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    busy = s.getsockname()[1]
    try:
        assert L.port_free(busy) is False
        found = L.find_free_port(busy)
        assert found != busy and found > busy
    finally:
        s.close()


def test_sem_nenhuma_porta_livre_levanta_erro_claro(monkeypatch):
    monkeypatch.setattr(L, "port_free", lambda p, host="127.0.0.1": False)
    with pytest.raises(OSError, match="nenhuma porta livre"):
        L.find_free_port(8000, tries=3)


# ---------------- sem console ----------------
def test_sem_console_stdout_none_nao_quebra(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    L.ensure_std_streams()
    print("nao quebra")  # nao levanta
    logging.getLogger("x").warning("nem o logging")
    assert sys.stdout is not None and sys.stderr is not None


# ---------------- bandeja ----------------
def test_bandeja_sem_pystray_segue_sem_derrubar(monkeypatch, tmp_path):
    real = builtins.__import__

    def fake(name, *a, **k):
        if name == "pystray":
            raise ImportError("sem pystray")
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", fake)
    assert L.start_tray("http://127.0.0.1:8000", tmp_path, lambda: None) is None


def test_bandeja_com_falha_ao_criar_icone_tambem_nao_derruba(monkeypatch, tmp_path):
    pystray = pytest.importorskip("pystray")  # so existe no Windows (a bandeja)

    class Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("sem area de notificacao")
    monkeypatch.setattr(pystray, "Icon", Boom)
    assert L.start_tray("http://127.0.0.1:8000", tmp_path, lambda: None) is None


def test_bandeja_monta_menu_abrir_registros_sair(monkeypatch, tmp_path):
    pystray = pytest.importorskip("pystray")
    seen = {}

    class FakeIcon:
        def __init__(self, name, image, title, menu):
            seen["items"] = [i.text for i in menu.items]
            seen["default"] = [i.text for i in menu.items if i.default]

        def run_detached(self):
            seen["rodou"] = True
    monkeypatch.setattr(pystray, "Icon", FakeIcon)
    assert L.start_tray("http://127.0.0.1:8000", tmp_path, lambda: None) is not None
    assert seen["items"] == ["Abrir o Jefrey", "Ver registros (para suporte)", "Sair"]
    assert seen["default"] == ["Abrir o Jefrey"] and seen["rodou"]


# ---------------- nuvem e o padrao ----------------
def test_modelo_local_so_e_baixado_se_a_pessoa_escolheu_local(tmp_path, monkeypatch):
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path))
    assert L.local_model_chosen() is False  # primeira execucao: nada escolhido
    from src.jefrey.core import llm_provider as lp
    lp.save_override("openai", "gpt-6-luna", "https://openrouter.ai/api", None, "sk-x")
    assert L.local_model_chosen() is False  # nuvem
    lp.save_override("ollama", "qwen3:1.7b", None, None, "")
    assert L.local_model_chosen() is True


# ---------------- sair pelo app ----------------
@pytest.fixture()
def client(monkeypatch):
    from src.jefrey.api import auth_middleware
    from src.jefrey.api.main import app
    auth_middleware._rl_buckets.clear()
    control.set_quit_hook(None)
    c = TestClient(app)
    h = {"Authorization": "Bearer " + c.post("/auth/dev-token", json={"user_id": "sair"}).json()["access_token"]}
    yield c, h
    control.set_quit_hook(None)


def test_sair_exige_login(client):
    c, _ = client
    assert c.post("/system/quit").status_code == 401


def test_sair_fora_do_modo_nativo_responde_404(client):
    c, h = client
    assert c.post("/system/quit", headers=h).status_code == 404


def test_sair_no_modo_nativo_chama_o_lancador_depois_de_responder(client):
    c, h = client
    chamado = []
    control.set_quit_hook(lambda: chamado.append(1))
    r = c.post("/system/quit", headers=h)
    assert r.status_code == 200 and r.json()["ok"] is True
    assert chamado == [1]


def test_control_sem_gancho_nao_faz_nada():
    control.set_quit_hook(None)
    assert control.can_quit() is False and control.request_quit() is False


def test_registros_em_arquivo_sobrevivem_ao_modulo_de_log_do_app(tmp_path):
    """O modulo de log do app zera os handlers ao ser importado; o arquivo tem que ser ligado depois dele."""
    import importlib
    import src.jefrey.core.logging as app_logging
    root = logging.getLogger()
    antes = list(root.handlers)
    try:
        importlib.reload(app_logging)  # simula a importacao: root.handlers = []
        path = L.setup_logging(tmp_path / "logs")
        logging.getLogger("src.jefrey.api.main").info("app subiu")
        for h in root.handlers:
            h.flush()
        assert "app subiu" in path.read_text(encoding="utf-8")
    finally:
        for h in list(root.handlers):
            if h not in antes:
                root.removeHandler(h)
                h.close()
