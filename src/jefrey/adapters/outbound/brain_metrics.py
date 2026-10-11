"""Medidas por cerebro (tempo ate o primeiro token e se deu certo) e feedback das respostas (👍/👎), no banco local.

So guarda numeros e o motivo curto da falha: nunca o texto da conversa nem chaves.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Optional, Sequence

from src.jefrey.domain.brain_rank import rank

WINDOW_DAYS = 7
FEEDBACK_VALUES = ("up", "down")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class BrainMetrics:
    def __init__(self):
        from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Table

        from src.jefrey.core.db import Base, get_engine

        meta = Base.metadata
        self.metrics = meta.tables.get("brain_metrics")
        if self.metrics is None:
            self.metrics = Table(
            "brain_metrics", meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("brain", String(300), nullable=False, index=True),
            Column("role", String(30), nullable=False, index=True),
            Column("seconds", Float, nullable=False),
            Column("ok", Boolean, nullable=False),
            Column("reason", String(120), nullable=False, default=""),
            Column("at", DateTime, nullable=False, index=True),
            )
        self.feedback = meta.tables.get("answer_feedback")
        if self.feedback is None:
            self.feedback = Table(
            "answer_feedback", meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("user_id", String(255), nullable=False),
            Column("message_id", String(120), nullable=False),
            Column("value", String(8), nullable=False),
            Column("note", String(300), nullable=False, default=""),
            Column("at", DateTime, nullable=False),
        )
        self.engine = get_engine()
        self.metrics.create(self.engine, checkfirst=True)
        self.feedback.create(self.engine, checkfirst=True)

    # ---- medidas por cerebro
    def record(self, brain: str, role: str, seconds: float, ok: bool, reason: str = "", now: Optional[datetime] = None) -> None:
        with self.engine.begin() as c:
            c.execute(self.metrics.insert().values(brain=brain[:300], role=role[:30], seconds=float(seconds), ok=bool(ok),
                                                   reason=(reason or "")[:120], at=now or _now()))

    def stats(self, role: str, now: Optional[datetime] = None, window_days: int = WINDOW_DAYS) -> dict:
        since = (now or _now()) - timedelta(days=window_days)
        t = self.metrics
        with self.engine.connect() as c:
            rows = c.execute(t.select().where((t.c.role == role) & (t.c.at >= since))).fetchall()
        per: dict[str, dict] = {}
        for r in rows:
            d = per.setdefault(r.brain, {"n": 0, "ok": 0, "secs": []})
            d["n"] += 1
            if r.ok:
                d["ok"] += 1
                d["secs"].append(float(r.seconds))
        return {k: {"n": d["n"], "ok": d["ok"], "median": median(d["secs"]) if d["secs"] else None} for k, d in per.items()}

    def ranking(self, role: str, keys: Sequence[str], now: Optional[datetime] = None) -> list[str]:
        return rank(keys, self.stats(role, now=now))

    # ---- feedback das respostas
    def add_feedback(self, user_id: str, message_id: str, value: str, note: str = "") -> None:
        if not user_id or user_id in ("system", "anonymous"):
            raise ValueError("usuario invalido")
        if value not in FEEDBACK_VALUES:
            raise ValueError("valor invalido: use up ou down")
        with self.engine.begin() as c:
            c.execute(self.feedback.insert().values(user_id=user_id, message_id=message_id[:120], value=value, note=(note or "")[:300], at=_now()))

    def feedback_counts(self) -> dict:
        t = self.feedback
        with self.engine.connect() as c:
            rows = c.execute(t.select()).fetchall()
        out = {v: 0 for v in FEEDBACK_VALUES}
        for r in rows:
            out[r.value] = out.get(r.value, 0) + 1
        return out
