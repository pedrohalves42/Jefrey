"""Cofre de chaves: protegido no Windows, legivel em formato antigo, nunca devolve lixo."""
import os

import pytest

from src.jefrey.core import secret_store as S


def test_ida_e_volta(tmp_path):
    f = tmp_path / "credentials" / "k"
    S.write_secret(f, "  sk-segredo-123  ")
    assert S.read_secret(f) == "sk-segredo-123"


@pytest.mark.skipif(os.name != "nt", reason="DPAPI so existe no Windows")
def test_no_windows_o_arquivo_nao_contem_a_chave_em_texto_puro(tmp_path):
    f = tmp_path / "k"
    S.write_secret(f, "sk-segredo-123")
    raw = f.read_text(encoding="utf-8")
    assert raw.startswith(S.PREFIX) and "sk-segredo-123" not in raw


@pytest.mark.skipif(os.name != "nt", reason="DPAPI so existe no Windows")
def test_dados_adulterados_nao_abrem(tmp_path):
    f = tmp_path / "k"
    S.write_secret(f, "sk-x")
    f.write_text(S.PREFIX + "AAAA", encoding="utf-8")
    assert S.read_secret(f) is None


def test_arquivo_antigo_em_texto_puro_continua_legivel(tmp_path):
    f = tmp_path / "k"
    f.write_text("sk-antigo\n", encoding="utf-8")
    assert S.read_secret(f) == "sk-antigo"


def test_ausente_ou_vazio_devolve_none(tmp_path):
    assert S.read_secret(tmp_path / "nao_existe") is None
    (tmp_path / "v").write_text("  \n", encoding="utf-8")
    assert S.read_secret(tmp_path / "v") is None


def test_gravacao_nao_deixa_temporario(tmp_path):
    S.write_secret(tmp_path / "k", "x")
    assert [p.name for p in tmp_path.iterdir()] == ["k"]


@pytest.mark.parametrize("i,ok", [("p1", True), ("open_router-2", True), ("", False), ("../x", False), ("A", False), ("x" * 41, False)])
def test_id_valido(i, ok):
    assert S.valid_id(i) is ok


def test_integracao_com_a_chave_do_llm(tmp_path, monkeypatch):
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path))
    from src.jefrey.core import llm_provider as lp
    lp.save_override("openai", "gpt-x", "https://openrouter.ai/api", None, "sk-nuvem")
    assert lp.load_saved_key() == "sk-nuvem"
    with pytest.raises(lp.LLMConfigError):  # nuvem sem chave e recusada
        lp.save_override("openai", "gpt-x", "https://openrouter.ai/api", None, "")
    assert lp.load_saved_key() == "sk-nuvem"  # a recusa nao apagou nada
    lp.save_override("ollama", "qwen3:1.7b", None, None, "")  # voltar ao local apaga a chave
    assert lp.load_saved_key() is None
