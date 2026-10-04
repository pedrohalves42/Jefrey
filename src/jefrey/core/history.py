"""Historico de conversa persistente (antes ficava na memoria do processo e sumia ao fechar o programa).

Isolado por (usuario, conversa). Guarda os ultimos turnos e apaga o que e antigo.
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

MAX_CONTENT = 4000
KEEP_DAYS = 90
_PURGE_EVERY = 100
_lock = threading.Lock()
_counter = 0


def _table():
    from sqlalchemy import Column, DateTime, Integer, String, Table, Text

    from src.jefrey.core.db import Base

    t = Base.metadata.tables.get("chat_history")
    if t is not None:
        return t
    return Table("chat_history", Base.metadata,
                 Column("id", Integer, primary_key=True, autoincrement=True),
                 Column("user_id", String(255), nullable=False, index=True),
                 Column("thread_id", String(300), nullable=False, index=True),
                 Column("role", String(12), nullable=False),
                 Column("content", Text, nullable=False),
                 Column("ts", DateTime, nullable=False, index=True))


class HistoryStore:
    def __init__(self):
        from src.jefrey.core.db import get_engine

        self.t = _table()
        self.engine = get_engine()
        self.t.create(self.engine, checkfirst=True)

    def add_turn(self, user_id: str, thread_id: str, user_text: str, answer: str, now: Optional[datetime] = None) -> None:
        global _counter
        if not user_id or user_id in ("system", "anonymous") or not thread_id:
            return
        ts = (now or datetime.now(timezone.utc)).replace(tzinfo=None)
        with self.engine.begin() as c:
            c.execute(self.t.insert(), [
                {"user_id": user_id, "thread_id": thread_id, "role": "user", "content": (user_text or "")[:MAX_CONTENT], "ts": ts},
                {"user_id": user_id, "thread_id": thread_id, "role": "assistant", "content": (answer or "")[:MAX_CONTENT], "ts": ts},
            ])
        with _lock:
            _counter += 1
            due = _counter % _PURGE_EVERY == 0
        if due:
            self.purge()

    def load(self, user_id: str, thread_id: str, max_messages: int = 24) -> list[dict]:
        with self.engine.connect() as c:
            rows = c.execute(self.t.select().where(self.t.c.user_id == user_id, self.t.c.thread_id == thread_id)
                             .order_by(self.t.c.id.desc()).limit(max_messages)).all()
        return [{"role": r.role, "content": r.content} for r in reversed(rows)]

    def clear_thread(self, user_id: str, thread_id: str) -> int:
        with self.engine.begin() as c:
            return c.execute(self.t.delete().where(self.t.c.user_id == user_id, self.t.c.thread_id == thread_id)).rowcount

    def purge(self, days: int = KEEP_DAYS) -> int:
        cut = (datetime.now(timezone.utc) - timedelta(days=days)).replace(tzinfo=None)
        with self.engine.begin() as c:
            return c.execute(self.t.delete().where(self.t.c.ts < cut)).rowcount
