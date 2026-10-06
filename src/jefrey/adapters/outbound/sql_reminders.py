"""Lembretes guardados no banco (SQLAlchemy), isolados por usuario. A regra de datas esta em domain/reminders.py."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.jefrey.domain.reminders import MAX_PENDING, MAX_TEXT, describe_due, local_tz

def _model():
    from sqlalchemy import Column, DateTime, String, Text
    from src.jefrey.core.db import Base

    existing = Base.metadata.tables.get("reminders")
    if existing is not None:
        return existing
    from sqlalchemy import Table
    return Table(
        "reminders", Base.metadata,
        Column("id", String(36), primary_key=True),
        Column("user_id", String(255), nullable=False, index=True),
        Column("text", Text, nullable=False),
        Column("due_at", DateTime, nullable=False, index=True),  # UTC sem fuso
        Column("repeat", String(10), nullable=False, default="none"),
        Column("status", String(10), nullable=False, default="pending"),  # pending | done | cancelled
        Column("created_at", DateTime, nullable=False),
    )


def _utc_naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _from_row(r) -> dict:
    due = r.due_at.replace(tzinfo=timezone.utc).astimezone(local_tz())
    return {"id": r.id, "text": r.text, "due_at": due.isoformat(), "due_label": describe_due(due),
            "repeat": r.repeat, "status": r.status}


class ReminderStore:
    """Tudo isolado por user_id: nunca le, apaga nem entrega lembrete de outro usuario."""

    def __init__(self):
        from src.jefrey.core.db import get_engine
        self.t = _model()
        self.engine = get_engine()
        self.t.create(self.engine, checkfirst=True)

    def add(self, user_id: str, text: str, due: datetime, repeat: str = "none") -> dict:
        from sqlalchemy import func, select
        if not user_id or user_id in ("system", "anonymous"):
            raise ValueError("usuario invalido")
        text = " ".join((text or "").split())[:MAX_TEXT]
        if not text:
            raise ValueError("lembrete vazio")
        if repeat not in ("none", "daily", "weekly"):
            raise ValueError("repeticao invalida")
        with self.engine.begin() as c:
            n = c.execute(select(func.count()).select_from(self.t).where(
                self.t.c.user_id == user_id, self.t.c.status == "pending")).scalar() or 0
            if n >= MAX_PENDING:
                raise ValueError(f"limite de {MAX_PENDING} lembretes pendentes")
            rid = str(uuid.uuid4())
            c.execute(self.t.insert().values(id=rid, user_id=user_id, text=text, due_at=_utc_naive(due),
                                             repeat=repeat, status="pending", created_at=_utc_naive(datetime.now(timezone.utc))))
            row = c.execute(self.t.select().where(self.t.c.id == rid)).one()
        return _from_row(row)

    def pending(self, user_id: str) -> list[dict]:
        with self.engine.connect() as c:
            rows = c.execute(self.t.select().where(self.t.c.user_id == user_id, self.t.c.status == "pending")
                             .order_by(self.t.c.due_at)).all()
        return [_from_row(r) for r in rows]

    def due(self, user_id: str, now: Optional[datetime] = None) -> list[dict]:
        cut = _utc_naive(now or datetime.now(timezone.utc))
        with self.engine.connect() as c:
            rows = c.execute(self.t.select().where(self.t.c.user_id == user_id, self.t.c.status == "pending",
                                                   self.t.c.due_at <= cut).order_by(self.t.c.due_at)).all()
        return [_from_row(r) for r in rows]

    def ack(self, user_id: str, rid: str, now: Optional[datetime] = None) -> bool:
        """A tela mostrou o lembrete: unico some; repetido vai para a proxima ocorrencia."""
        now_utc = _utc_naive(now or datetime.now(timezone.utc))
        with self.engine.begin() as c:
            row = c.execute(self.t.select().where(self.t.c.id == rid, self.t.c.user_id == user_id,
                                                  self.t.c.status == "pending")).first()
            if row is None:
                return False
            if row.repeat == "none":
                c.execute(self.t.update().where(self.t.c.id == rid).values(status="done"))
            else:
                step = timedelta(days=1 if row.repeat == "daily" else 7)
                nxt = row.due_at
                while nxt <= now_utc:
                    nxt += step
                c.execute(self.t.update().where(self.t.c.id == rid).values(due_at=nxt))
        return True

    def cancel(self, user_id: str, rid: str) -> bool:
        with self.engine.begin() as c:
            res = c.execute(self.t.update().where(self.t.c.id == rid, self.t.c.user_id == user_id,
                                                  self.t.c.status == "pending").values(status="cancelled"))
        return res.rowcount > 0
