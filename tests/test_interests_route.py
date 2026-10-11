import asyncio

import pytest

from src.jefrey.api import today_routes as R
from src.jefrey.core import today as T


@pytest.fixture(autouse=True)
def limpo(tmp_path, monkeypatch):
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path))
    T._cache.clear()


class Req:
    def __init__(self, uid):
        class S:
            pass
        self.state = S()
        self.state.user_id = uid


def test_assuntos_trazem_sugestoes_do_que_o_jefrey_aprendeu(tmp_path, monkeypatch):
    from sqlalchemy import create_engine

    import src.jefrey.core.db as dbm
    from src.jefrey.core.learning import FactStore

    eng = create_engine(f"sqlite:///{tmp_path}/i.db")
    monkeypatch.setattr(dbm, "get_engine", lambda: eng)
    FactStore().teach("ana", "Adoro futebol e meu time joga todo domingo", "gosto")
    out = asyncio.run(R.get_interests(Req("ana")))
    assert out["suggested"][0] == "esportes" and out["selected"] == []
    T.save_interests(["esportes"])
    assert "esportes" not in asyncio.run(R.get_interests(Req("ana")))["suggested"]
