"""Diagnostico do lancamento: o programa instalado deixa uma marca em logs/arranque.txt mesmo se o log de arquivo falhar."""
from pathlib import Path

from src.jefrey.native import launcher as L


def test_marca_de_arranque_grava_pid_e_versao(tmp_path):
    arq = L.escrever_marca_arranque(tmp_path / "logs", "iniciando teste")
    txt = arq.read_text(encoding="utf-8")
    assert arq.name == "arranque.txt" and "iniciando teste" in txt and "pid=" in txt


def test_falha_do_log_de_arquivo_nao_some_em_silencio(tmp_path, monkeypatch):
    def quebra(_):
        raise OSError("disco cheio")
    monkeypatch.setattr(L, "setup_logging", quebra)
    arq = L.iniciar_logs(tmp_path / "logs")
    assert arq is None
    txt = (tmp_path / "logs" / "arranque.txt").read_text(encoding="utf-8")
    assert "falhou" in txt and "disco cheio" in txt
