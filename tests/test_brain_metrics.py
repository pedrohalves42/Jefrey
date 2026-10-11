"""Tarefa 3 do plano: medidas por cerebro e feedback (👍/👎) guardados no banco local."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine

AGORA = datetime(2026, 10, 11, 12, 0, 0)


@pytest.fixture()
def store(tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path}/m.db")
    import src.jefrey.core.db as dbm
    monkeypatch.setattr(dbm, "get_engine", lambda: eng)
    from src.jefrey.adapters.outbound.brain_metrics import BrainMetrics
    return BrainMetrics()


def test_groq_rapido_passa_na_frente_do_gemini_lento(store):
    for _ in range(10):
        store.record("groq", "conversa", 0.5, True, now=AGORA)
        store.record("gemini", "conversa", 20.0, True, now=AGORA)
    assert store.ranking("conversa", ["gemini", "groq"], now=AGORA) == ["groq", "gemini"]


def test_falha_conta_contra_o_cerebro_e_o_motivo_fica_guardado(store):
    for _ in range(10):
        store.record("rapido", "conversa", 0.3, False, reason="429", now=AGORA)
        store.record("firme", "conversa", 4.0, True, now=AGORA)
    assert store.ranking("conversa", ["rapido", "firme"], now=AGORA) == ["firme", "rapido"]
    assert store.stats("conversa", now=AGORA)["rapido"]["ok"] == 0


def test_so_a_ultima_semana_conta(store):
    for _ in range(10):
        store.record("antigo", "conversa", 30.0, True, now=AGORA - timedelta(days=9))
        store.record("novo", "conversa", 1.0, True, now=AGORA)
        store.record("antigo", "conversa", 1.0, True, now=AGORA)
    assert store.stats("conversa", now=AGORA)["antigo"]["median"] == 1.0


def test_funcoes_sao_medidas_separadamente(store):
    for _ in range(10):
        store.record("a", "rapido", 0.5, True, now=AGORA)
        store.record("a", "escrita", 15.0, True, now=AGORA)
    assert store.stats("rapido", now=AGORA)["a"]["median"] == 0.5
    assert store.stats("escrita", now=AGORA)["a"]["median"] == 15.0


def test_feedback_guarda_e_recusa_valor_invalido(store):
    store.add_feedback("pedro", "msg-1", "down", note="inventou a fonte")
    store.add_feedback("pedro", "msg-2", "up")
    assert store.feedback_counts() == {"up": 1, "down": 1}
    with pytest.raises(ValueError):
        store.add_feedback("pedro", "msg-3", "talvez")
    with pytest.raises(ValueError):
        store.add_feedback("anonymous", "msg-4", "up")
