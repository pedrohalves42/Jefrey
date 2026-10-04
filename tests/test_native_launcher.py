"""Modo nativo: configuracao automatica, segredos persistentes e porta so local."""
import json

from src.jefrey.native import launcher as L


def test_segredos_sao_gerados_uma_vez_e_reaproveitados(tmp_path):
    a = L.ensure_secrets(tmp_path)
    b = L.ensure_secrets(tmp_path)
    assert a == b and len(a["api_secret"]) >= 32 and len(a["hmac_key"]) >= 32
    assert a["api_secret"] != a["hmac_key"]


def test_arquivo_de_segredos_corrompido_e_refeito(tmp_path):
    (tmp_path / "native_secrets.json").write_text("{lixo", encoding="utf-8")
    s = L.ensure_secrets(tmp_path)
    assert len(s["api_secret"]) >= 32
    assert json.loads((tmp_path / "native_secrets.json").read_text())["api_secret"] == s["api_secret"]


def test_segredo_curto_demais_e_substituido(tmp_path):
    (tmp_path / "native_secrets.json").write_text(json.dumps({"api_secret": "curta", "hmac_key": "x" * 40}))
    s = L.ensure_secrets(tmp_path)
    assert len(s["api_secret"]) >= 32 and s["hmac_key"] == "x" * 40


def test_ambiente_nativo_usa_sqlite_e_a_pasta_do_usuario(tmp_path):
    env = L.build_env(tmp_path, base={})
    assert env["JEFREY_MODE"] == "native"
    assert env["JEFREY_DATABASE__URL"].startswith("sqlite:///") and str(tmp_path.as_posix()) in env["JEFREY_DATABASE__URL"]
    assert env["JEFREY_CONFIG_DIR"] == str(tmp_path / "config")
    assert env["JEFREY_FILES_DIR"].startswith(str(tmp_path))
    assert env["JEFREY_MEMORY__LONG_TERM__PERSIST_DIRECTORY"].startswith(str(tmp_path))
    assert env["JEFREY_LLM__BASE_URL"] == L.OLLAMA_URL
    for d in ("data", "data/files", "data/chroma_db", "config"):
        assert (tmp_path / d).is_dir()


def test_nunca_exposto_na_rede_mesmo_que_o_ambiente_peca(tmp_path):
    env = L.build_env(tmp_path, base={"JEFREY_API_HOST": "0.0.0.0"})
    assert env["JEFREY_API_HOST"] == "127.0.0.1"


def test_modo_nativo_nao_pode_ser_desligado_por_variavel(tmp_path):
    assert L.build_env(tmp_path, base={"JEFREY_MODE": "docker"})["JEFREY_MODE"] == "native"


def test_configuracao_do_usuario_tem_prioridade(tmp_path):
    env = L.build_env(tmp_path, base={"JEFREY_LLM__BASE_URL": "http://192.168.0.9:11434", "OUTRA": "x"})
    assert env["JEFREY_LLM__BASE_URL"] == "http://192.168.0.9:11434"
    assert "OUTRA" not in env  # so as variaveis do Jefrey


def test_porta_personalizada(tmp_path):
    assert L.build_env(tmp_path, base={}, port=8123)["JEFREY_API_PORT"] == "8123"


def test_modelos_faltantes():
    assert L.missing_models([]) == ["qwen3:1.7b", "embeddinggemma"]
    assert L.missing_models(["qwen3:1.7b", "embeddinggemma:latest", "outro:1b"]) == []
    assert L.missing_models(["qwen3:4b", "embeddinggemma:latest"]) == ["qwen3:1.7b"]  # tag exata quando ha tag


def test_ollama_ausente_da_mensagem_clara(monkeypatch):
    monkeypatch.setattr(L, "ollama_up", lambda *a, **k: False)
    monkeypatch.setattr(L, "find_ollama", lambda: None)
    ok, msg = L.ensure_ollama()
    assert ok is False and "ollama.com/download" in msg


def test_ollama_ja_rodando_nao_inicia_outro(monkeypatch):
    monkeypatch.setattr(L, "ollama_up", lambda *a, **k: True)
    called = []
    monkeypatch.setattr(L.subprocess, "Popen", lambda *a, **k: called.append(1))
    assert L.ensure_ollama()[0] is True and called == []
