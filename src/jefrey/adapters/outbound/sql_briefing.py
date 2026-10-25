"""Resumo do dia guardado no banco (SQLAlchemy). As regras do texto ficam em domain/briefing.py."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import inspect, select

from src.jefrey.domain.briefing import DEFAULT_HOUR


def _tables():
    from sqlalchemy import Boolean, Column, DateTime, Integer, String, Table, Text

    from src.jefrey.core.db import Base

    md = Base.metadata
    br = md.tables.get("briefings")
    if br is None:
        br = Table("briefings", md, Column("user_id", String(255), primary_key=True), Column("day", String(10), primary_key=True),
                   Column("text", Text, nullable=False), Column("seen", Boolean, nullable=False), Column("created_at", DateTime, nullable=False))
    pr = md.tables.get("proactive_prefs")
    if pr is None:
        pr = Table("proactive_prefs", md, Column("user_id", String(255), primary_key=True), Column("enabled", Boolean, nullable=False),
                   Column("hour", Integer, nullable=False), Column("notify", Boolean, nullable=False))
    return br, pr


class BriefingStore:
    def __init__(self):
        from src.jefrey.core.db import get_engine

        self.t, self.prefs = _tables()
        self.engine = get_engine()
        self.t.create(self.engine, checkfirst=True)
        self.prefs.create(self.engine, checkfirst=True)

    def get_prefs(self, user_id: str) -> dict:
        with self.engine.connect() as c:
            r = c.execute(self.prefs.select().where(self.prefs.c.user_id == user_id)).first()
        return {"enabled": True, "hour": DEFAULT_HOUR, "notify": True} if r is None else {"enabled": bool(r.enabled), "hour": int(r.hour), "notify": bool(r.notify)}

    def set_prefs(self, user_id: str, *, enabled: Optional[bool] = None, hour: Optional[int] = None, notify: Optional[bool] = None) -> dict:
        if not user_id or user_id in ("system", "anonymous"):
            raise ValueError("usuario invalido")
        cur = self.get_prefs(user_id)
        if enabled is not None:
            cur["enabled"] = bool(enabled)
        if notify is not None:
            cur["notify"] = bool(notify)
        if hour is not None:
            if not 5 <= hour <= 12:
                raise ValueError("O resumo da manhã pode ser entre 5h e 12h.")
            cur["hour"] = int(hour)
        with self.engine.begin() as c:
            c.execute(self.prefs.delete().where(self.prefs.c.user_id == user_id))
            c.execute(self.prefs.insert().values(user_id=user_id, **cur))
        return cur

    def get(self, user_id: str, day: str) -> Optional[dict]:
        with self.engine.connect() as c:
            r = c.execute(self.t.select().where((self.t.c.user_id == user_id) & (self.t.c.day == day))).first()
        return {"day": r.day, "text": r.text, "seen": bool(r.seen)} if r else None

    def all(self, user_id: str, limit: int = 400) -> list[dict]:
        with self.engine.connect() as c:
            rows = c.execute(self.t.select().where(self.t.c.user_id == user_id).order_by(self.t.c.day.desc()).limit(limit)).fetchall()
        return [{"day": r.day, "text": r.text} for r in rows]

    def put(self, user_id: str, day: str, text: str) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self.engine.begin() as c:
            c.execute(self.t.delete().where((self.t.c.user_id == user_id) & (self.t.c.day == day)))
            c.execute(self.t.insert().values(user_id=user_id, day=day, text=text[:1500], seen=False, created_at=now))

    def mark_seen(self, user_id: str, day: str) -> bool:
        with self.engine.begin() as c:
            return bool(c.execute(self.t.update().where((self.t.c.user_id == user_id) & (self.t.c.day == day)).values(seen=True)).rowcount)

    def forget_all(self, user_id: str) -> int:
        with self.engine.begin() as c:
            c.execute(self.prefs.delete().where(self.prefs.c.user_id == user_id))
            return c.execute(self.t.delete().where(self.t.c.user_id == user_id)).rowcount or 0


def known_users() -> list[str]:
    """Pessoas conhecidas (com nome, fatos, assuntos ou lembretes)."""
    from src.jefrey.core.db import Base, get_engine

    eng = get_engine()
    insp = inspect(eng)
    ids: set[str] = set()
    with eng.connect() as c:
        for name in ("user_profile", "learned_facts", "study_topics", "reminders"):
            t = Base.metadata.tables.get(name)
            if t is not None and insp.has_table(name):
                ids |= {r[0] for r in c.execute(select(t.c.user_id).distinct())}
    return sorted(u for u in ids if u and u not in ("system", "anonymous"))
