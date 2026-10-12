"""/audit/today: so para quem esta logado e so as acoes da propria pessoa."""
import asyncio
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.jefrey.api import audit_routes as AR


class Req:
    def __init__(self, uid="pedro"):
        self.state = type("S", (), {"user_id": uid})()


def test_sem_login_nega():
    with pytest.raises(HTTPException) as e:
        asyncio.run(AR.today(Req("anonymous")))
    assert e.value.status_code == 401


def test_so_acoes_da_propria_pessoa(tmp_path, monkeypatch):
    from contextlib import contextmanager

    from src.jefrey.core.models import AuditLog

    eng = create_engine(f"sqlite:///{tmp_path}/a.db")
    AuditLog.__table__.create(bind=eng)
    Session = sessionmaker(bind=eng)

    @contextmanager
    def fake_db():
        s = Session()
        try:
            yield s
            s.commit()
        finally:
            s.close()

    import src.jefrey.core.db as dbm
    monkeypatch.setattr(dbm, "get_db", fake_db)
    with fake_db() as s:
        for uid, dec in (("pedro", "allow"), ("pedro", "deny"), ("outra", "allow")):
            s.add(AuditLog(id=uuid.uuid4(), user_id=uid, thread_id="t", tool_name="cancel_reminder", actor_role="user",
                           risk="medium", decision=dec, source="agent"))
    r = asyncio.run(AR.today(Req("pedro")))
    assert r["feitos"] == 1 and r["barrados"] == 1 and len(r["itens"]) == 2
