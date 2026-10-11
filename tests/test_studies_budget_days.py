"""Teto de gasto dos estudos (US$ 0,10/dia) ao longo de varios dias, com data simulada."""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine

from src.jefrey.core import studies as S

TZ = ZoneInfo("America/Sao_Paulo")


def run(c):
    return asyncio.run(c)


@pytest.fixture()
def st(tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path}/b.db")
    import src.jefrey.core.db as dbm
    monkeypatch.setattr(dbm, "get_engine", lambda: eng)
    return S.StudyStore()


class Cliente:
    config = type("C", (), {"is_cloud": True})()

    async def chat(self, messages):
        return "x" * 4000


def _quando(monkeypatch, iso):
    class FakeDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromisoformat(iso).replace(tzinfo=tz or TZ)
    monkeypatch.setattr("src.jefrey.application.studies.datetime", FakeDT)


def test_padrao_e_dez_centavos(st):
    assert st.get_prefs("ana")["budget_usd"] == 0.10 and S.DEFAULT_BUDGET_USD == 0.10


def test_estudo_para_ao_bater_o_teto_e_volta_no_dia_seguinte(st, monkeypatch):
    st.get_prefs("ana")
    hoje = "2026-10-05"
    b = S._Budget(st, "ana", hoje, 0.10)
    gasto = 0.0
    chamadas = 0
    with pytest.raises(S.StudyError, match="limite de gasto de hoje"):
        for _ in range(500):  # bem mais do que o teto permite
            run(b.ask(Cliente(), [{"role": "user", "content": "y" * 4000}], 4000))
            chamadas += 1
    gasto = st.spent_today("ana", hoje)
    assert 0 < chamadas < 500 and gasto <= 0.10 + 0.02  # nunca passa do teto (alem de uma ultima chamada pequena)
    # amanha o orcamento e novo
    assert st.spent_today("ana", "2026-10-06") == 0.0
    run(S._Budget(st, "ana", "2026-10-06", 0.10).ask(Cliente(), [{"role": "user", "content": "oi"}], 100))
    assert st.spent_today("ana", "2026-10-06") > 0


def test_eligible_respeita_teto_horario_de_silencio_e_ociosidade(st, monkeypatch):
    _quando(monkeypatch, "2026-10-05T14:00:00")
    assert S.eligible("ana", TZ, idle_s=600, store=st) is True
    assert S.eligible("ana", TZ, idle_s=10, store=st) is False  # a pessoa esta usando o computador
    st.charge("ana", "2026-10-05", 0.099)
    assert S.eligible("ana", TZ, idle_s=600, store=st) is False  # sobrou menos que uma chamada minima
    _quando(monkeypatch, "2026-10-06T14:00:00")
    assert S.eligible("ana", TZ, idle_s=600, store=st) is True  # outro dia, orcamento novo
    _quando(monkeypatch, "2026-10-06T23:30:00")
    assert S.eligible("ana", TZ, idle_s=600, store=st) is False  # horario de silencio (22h as 7h)


def test_teto_zero_ou_desligado_nao_estuda(st, monkeypatch):
    _quando(monkeypatch, "2026-10-05T14:00:00")
    st.set_prefs("ana", budget_usd=0)
    assert S.eligible("ana", TZ, idle_s=600, store=st) is False
    st.set_prefs("ana", budget_usd=0.1, enabled=False)
    assert S.eligible("ana", TZ, idle_s=600, store=st) is False


def test_teto_maximo_de_cinco_dolares(st):
    with pytest.raises(Exception):
        st.set_prefs("ana", budget_usd=6)


def test_so_estuda_com_modelo_de_nuvem(st):
    class Local:
        config = type("C", (), {"is_cloud": False})()
    assert S._is_cloud(Local()) is False and S._is_cloud(Cliente()) is True


def test_gasto_de_uma_pessoa_nao_afeta_a_outra(st):
    st.charge("ana", "2026-10-05", 0.09)
    assert st.spent_today("bob", "2026-10-05") == 0.0
