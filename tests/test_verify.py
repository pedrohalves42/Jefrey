"""Acoes confirmadas: nunca afirma sucesso sem achar o resultado na releitura."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine

from src.jefrey.domain.verify import NOT_CONFIRMED, confirm_created, confirm_removed


def test_criado_e_relido_confirma():
    assert confirm_created("Pronto!", {"id": "a1"}, "a1") == "Pronto!"


def test_nao_achou_ou_outro_registro_nao_confirma():
    assert confirm_created("Pronto!", None, "a1") == NOT_CONFIRMED
    assert confirm_created("Pronto!", {"id": "outro"}, "a1") == NOT_CONFIRMED


def test_cancelamento_so_confirma_se_sumiu():
    assert confirm_removed("Cancelado.", still_there=False) == "Cancelado."
    assert "ainda aparece" in confirm_removed("Cancelado.", still_there=True)


@pytest.fixture
def banco(tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path}/v.db")
    import src.jefrey.core.db as db
    monkeypatch.setattr(db, "get_engine", lambda: eng)


def test_lembrete_criado_diz_o_horario_e_confirma(banco):
    from src.jefrey.skills.reminders import RemindersSkill

    out = asyncio.run(RemindersSkill().set_reminder.ainvoke({"text": "ligar pro dentista", "when": "amanha as 10h", "user_id": "pedro"}))
    assert "Vou te lembrar" in out and "10:00" in out


def test_lembrete_nao_relido_nao_afirma_sucesso(banco, monkeypatch):
    from src.jefrey.adapters.outbound import sql_reminders as SR
    from src.jefrey.skills.reminders import RemindersSkill

    monkeypatch.setattr(SR.ReminderStore, "pending", lambda self, uid: [], raising=False)
    out = asyncio.run(RemindersSkill().set_reminder.ainvoke({"text": "ligar pro dentista", "when": "amanha as 10h", "user_id": "pedro"}))
    assert "Não consegui confirmar" in out and "Vou te lembrar" not in out
