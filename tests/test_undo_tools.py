"""Tarefa 7: o diario de desfazer ligado as ferramentas reais (lembrete e arquivo) e a frase 'desfaz isso'."""
import asyncio

import pytest

from src.jefrey.application import undo as U
from src.jefrey.application.agent_loop import route_intent


def run(c):
    return asyncio.run(c)


@pytest.fixture()
def diario(tmp_path, monkeypatch):
    j = U.UndoJournal(tmp_path / "undo.json")
    monkeypatch.setattr(U, "shared_journal", lambda: j)
    return j


def test_frases_de_desfazer_vao_direto_para_a_ferramenta():
    for f in ("desfaz isso", "Desfazer", "desfaz a ultima acao", "voltar atras", "volta atras"):
        assert route_intent(f) == ("undo_last", {}), f
    assert route_intent("me lembra de ligar amanha as 10")[0] == "set_reminder"


def test_gravar_arquivo_registra_o_conteudo_anterior_e_desfazer_restaura(tmp_path, monkeypatch, diario):
    from src.jefrey.skills import essentials as E

    alvo = tmp_path / "nota.txt"
    alvo.write_text("versao 1", encoding="utf-8")
    monkeypatch.setattr(E, "safe_path", lambda uid, p: alvo)
    sk = E.EssentialsSkill() if hasattr(E, "EssentialsSkill") else None
    assert sk is not None
    run(sk.files_write(path="nota.txt", content="versao 2", user_id="pedro"))
    assert alvo.read_text(encoding="utf-8") == "versao 2"
    from src.jefrey.skills.undo import UNDOERS
    msg = diario.undo_last("pedro", UNDOERS)
    assert alvo.read_text(encoding="utf-8") == "versao 1" and "desfiz" in msg.lower()


def test_arquivo_novo_e_apagado_ao_desfazer(tmp_path, monkeypatch, diario):
    from src.jefrey.skills import essentials as E
    from src.jefrey.skills.undo import UNDOERS

    alvo = tmp_path / "novo.txt"
    monkeypatch.setattr(E, "safe_path", lambda uid, p: alvo)
    run(E.EssentialsSkill().files_write(path="novo.txt", content="oi", user_id="pedro"))
    assert alvo.exists()
    diario.undo_last("pedro", UNDOERS)
    assert not alvo.exists()
