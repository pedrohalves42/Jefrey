"""Tarefa 3 do plano: 👍/👎 em cada resposta e medidas por cerebro, via API (so para quem esta logado)."""
import asyncio

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine

from src.jefrey.api import feedback_routes as FR


def run(c):
    return asyncio.run(c)


class Req:
    def __init__(self, uid="pedro"):
        self.state = type("S", (), {"user_id": uid})()


@pytest.fixture(autouse=True)
def banco(tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path}/f.db")
    import src.jefrey.core.db as dbm
    monkeypatch.setattr(dbm, "get_engine", lambda: eng)
    from src.jefrey.adapters.outbound.brain_metrics import BrainMetrics
    store = BrainMetrics()
    monkeypatch.setattr(FR, "_store", lambda: store)
    return store


def test_feedback_positivo_e_negativo_ficam_guardados(banco):
    assert run(FR.send_feedback(Req(), FR.FeedbackBody(message_id="m1", value="up")))["ok"] is True
    run(FR.send_feedback(Req(), FR.FeedbackBody(message_id="m2", value="down", note="inventou a fonte")))
    assert banco.feedback_counts() == {"up": 1, "down": 1}


def test_valor_invalido_e_recusado():
    with pytest.raises(ValidationError):
        FR.FeedbackBody(message_id="m1", value="talvez")


def test_sem_login_nao_grava():
    with pytest.raises(HTTPException) as e:
        run(FR.send_feedback(Req("anonymous"), FR.FeedbackBody(message_id="m1", value="up")))
    assert e.value.status_code == 401


def test_resumo_de_feedback_para_a_tela(banco):
    run(FR.send_feedback(Req(), FR.FeedbackBody(message_id="m1", value="down")))
    out = run(FR.feedback_summary(Req()))
    assert out == {"up": 0, "down": 1}


def test_medidas_por_cerebro_listam_funcao_e_numeros(banco):
    for _ in range(6):
        banco.record("groq", "rapido", 0.5, True)
    out = run(FR.brain_metrics(Req(), role="rapido"))
    assert out["role"] == "rapido" and out["brains"]["groq"]["n"] == 6
