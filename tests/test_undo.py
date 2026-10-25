"""Tarefa 7 do plano: desfazer o que o Jefrey fez. Diario por pessoa; o que nao tem volta (enviar mensagem) e dito com clareza."""
from datetime import datetime, timedelta

from src.jefrey.application.undo import UndoJournal

AGORA = datetime(2026, 10, 11, 12, 0, 0)


def _diario(tmp_path):
    return UndoJournal(tmp_path / "undo.json")


def test_desfaz_a_acao_mais_recente_primeiro(tmp_path):
    j = _diario(tmp_path)
    feitos = []
    j.record("pedro", "lembrete: dentista", "delete_reminder", {"id": "r1"}, now=AGORA)
    j.record("pedro", "nota: lista de compras", "delete_note", {"id": "n1"}, now=AGORA + timedelta(minutes=1))
    undoers = {"delete_reminder": lambda p: feitos.append(("lembrete", p["id"])), "delete_note": lambda p: feitos.append(("nota", p["id"]))}
    msg = j.undo_last("pedro", undoers, now=AGORA + timedelta(minutes=2))
    assert feitos == [("nota", "n1")] and "lista de compras" in msg
    j.undo_last("pedro", undoers, now=AGORA + timedelta(minutes=3))
    assert feitos[-1] == ("lembrete", "r1")


def test_sem_nada_para_desfazer(tmp_path):
    assert "nada para desfazer" in _diario(tmp_path).undo_last("pedro", {}, now=AGORA).lower()


def test_acao_sem_volta_e_dita_com_clareza(tmp_path):
    j = _diario(tmp_path)
    j.record("pedro", "mensagem enviada a Maria", "irreversible", {}, now=AGORA)
    msg = j.undo_last("pedro", {}, now=AGORA)
    assert "não dá para desfazer" in msg.lower() and "mensagem enviada a Maria" in msg


def test_so_vale_para_as_ultimas_24_horas(tmp_path):
    j = _diario(tmp_path)
    j.record("pedro", "nota antiga", "delete_note", {"id": "n9"}, now=AGORA - timedelta(hours=30))
    assert "nada para desfazer" in j.undo_last("pedro", {"delete_note": lambda p: None}, now=AGORA).lower()


def test_cada_pessoa_so_desfaz_o_que_e_dela(tmp_path):
    j = _diario(tmp_path)
    feitos = []
    j.record("ana", "nota da Ana", "delete_note", {"id": "a1"}, now=AGORA)
    assert "nada para desfazer" in j.undo_last("pedro", {"delete_note": lambda p: feitos.append(p)}, now=AGORA).lower()
    assert feitos == []


def test_desfazer_que_falha_nao_some_com_a_entrada(tmp_path):
    j = _diario(tmp_path)
    j.record("pedro", "nota", "delete_note", {"id": "n1"}, now=AGORA)

    def quebra(_p):
        raise RuntimeError("banco ocupado")
    msg = j.undo_last("pedro", {"delete_note": quebra}, now=AGORA)
    assert "não consegui desfazer" in msg.lower()
    assert j.last("pedro", now=AGORA) is not None  # continua na lista para tentar de novo


def test_o_diario_sobrevive_a_reiniciar(tmp_path):
    _diario(tmp_path).record("pedro", "nota", "delete_note", {"id": "n1"}, now=AGORA)
    assert _diario(tmp_path).last("pedro", now=AGORA)["label"] == "nota"
