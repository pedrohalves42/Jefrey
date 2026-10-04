"""O endereco do Ollama local vem do ambiente (docker ou nativo), nao de arquivo salvo."""
import json

import pytest

from src.jefrey.core import llm_provider as lp


@pytest.fixture()
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path))
    return tmp_path


def test_arquivo_antigo_com_endereco_do_docker_e_ignorado(cfg):
    (cfg / "llm.runtime.json").write_text(json.dumps({"provider": "ollama", "model": "m", "base_url": "http://ollama:11434"}))
    assert "base_url" not in lp.load_override()


def test_ambiente_nativo_vence_o_arquivo_antigo(cfg, monkeypatch):
    (cfg / "llm.runtime.json").write_text(json.dumps({"provider": "ollama", "model": "qwen3:1.7b", "base_url": "http://ollama:11434"}))
    from src.jefrey.core.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s.llm, "base_url", "http://localhost:11434")
    assert lp.config_from_settings(s).base_url == "http://localhost:11434"


def test_salvar_nao_grava_o_endereco_padrao_do_ollama(cfg):
    lp.save_override("ollama", "qwen3:1.7b", "http://ollama:11434", None, None)
    assert json.loads((cfg / "llm.runtime.json").read_text())["base_url"] is None
    lp.save_override("ollama", "qwen3:1.7b", None, None, None)
    assert json.loads((cfg / "llm.runtime.json").read_text())["base_url"] is None


def test_endereco_personalizado_do_usuario_e_respeitado(cfg):
    lp.save_override("ollama", "m", "http://192.168.0.9:11434/", None, None)
    assert json.loads((cfg / "llm.runtime.json").read_text())["base_url"] == "http://192.168.0.9:11434"
    assert lp.load_override()["base_url"] == "http://192.168.0.9:11434"


def test_outros_provedores_nao_sao_afetados(cfg):
    lp.save_override("openai", "gpt-4o-mini", None, None, "sk-teste")
    assert json.loads((cfg / "llm.runtime.json").read_text())["provider"] == "openai"
