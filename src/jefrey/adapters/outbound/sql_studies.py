"""Estudos guardados no banco (SQLAlchemy): assuntos, guias, fontes, preferencias e gasto do dia. As regras ficam em domain/studies.py."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select

from src.jefrey.domain.learning import has_secret, sensitivity_for
from src.jefrey.domain.urls import site_domain
from src.jefrey.domain.studies import (
    DEFAULT_BUDGET_USD, LEVEL_MAX, MAX_ACTIVE_TOPICS, MAX_SOURCES, StudyError, _norm, clean_source_url, level_label,
)

# ---------------- tabelas ----------------
def _tables():
    from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Table, Text
    from sqlalchemy import JSON

    from src.jefrey.core.db import Base

    md = Base.metadata
    topics = md.tables.get("study_topics")
    if topics is None:
        topics = Table("study_topics", md,
                       Column("id", String(40), primary_key=True), Column("user_id", String(255), nullable=False, index=True),
                       Column("title", String(80), nullable=False), Column("norm", String(80), nullable=False),
                       Column("status", String(10), nullable=False), Column("level", Integer, nullable=False),
                       Column("source", String(12), nullable=False), Column("created_at", DateTime, nullable=False),
                       Column("last_studied_at", DateTime, nullable=True), Column("last_error", String(200), nullable=True))
    guides = md.tables.get("study_guides")
    if guides is None:
        guides = Table("study_guides", md,
                       Column("id", String(40), primary_key=True), Column("topic_id", String(40), nullable=False, index=True),
                       Column("user_id", String(255), nullable=False, index=True), Column("title", String(120), nullable=False),
                       Column("summary", Text, nullable=False), Column("body", Text, nullable=False),
                       Column("sources", JSON, nullable=False), Column("level", Integer, nullable=False),
                       Column("created_at", DateTime, nullable=False))
    prefs = md.tables.get("study_prefs")
    if prefs is None:
        prefs = Table("study_prefs", md,
                      Column("user_id", String(255), primary_key=True), Column("enabled", Boolean, nullable=False),
                      Column("budget_usd", Float, nullable=False), Column("quiet_start", Integer, nullable=False),
                      Column("quiet_end", Integer, nullable=False))
    spend = md.tables.get("study_spend")
    if spend is None:
        spend = Table("study_spend", md,
                      Column("user_id", String(255), primary_key=True), Column("day", String(10), primary_key=True),
                      Column("usd", Float, nullable=False))
    return topics, guides, prefs, spend


def _sources_table():
    from sqlalchemy import Column, DateTime, String, Table

    from src.jefrey.core.db import Base

    t = Base.metadata.tables.get("study_sources")
    if t is None:
        t = Table("study_sources", Base.metadata,
                  Column("id", String(40), primary_key=True), Column("user_id", String(255), nullable=False, index=True),
                  Column("topic_id", String(40), nullable=True, index=True), Column("url", String(600), nullable=False),
                  Column("title", String(160), nullable=False), Column("created_at", DateTime, nullable=False))
    return t


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class StudyStore:
    def __init__(self):
        from src.jefrey.core.db import get_engine

        self.topics, self.guides, self.prefs, self.spend = _tables()
        self.engine = get_engine()
        self.sources = _sources_table()
        for t in (self.topics, self.guides, self.prefs, self.spend, self.sources):
            t.create(self.engine, checkfirst=True)

    @staticmethod
    def _check(user_id: str) -> None:
        if not user_id or user_id in ("system", "anonymous"):
            raise ValueError("usuario invalido")

    # --- preferencias ---
    def get_prefs(self, user_id: str) -> dict:
        with self.engine.connect() as c:
            r = c.execute(self.prefs.select().where(self.prefs.c.user_id == user_id)).first()
        if r is None:
            return {"enabled": True, "budget_usd": DEFAULT_BUDGET_USD, "quiet_start": 22, "quiet_end": 7}
        return {"enabled": bool(r.enabled), "budget_usd": float(r.budget_usd), "quiet_start": int(r.quiet_start), "quiet_end": int(r.quiet_end)}

    def set_prefs(self, user_id: str, *, enabled: Optional[bool] = None, budget_usd: Optional[float] = None,
                  quiet_start: Optional[int] = None, quiet_end: Optional[int] = None) -> dict:
        self._check(user_id)
        cur = self.get_prefs(user_id)
        if enabled is not None:
            cur["enabled"] = bool(enabled)
        if budget_usd is not None:
            if not 0 <= budget_usd <= 5:
                raise ValueError("O limite diário deve ficar entre 0 e 5 dólares.")
            cur["budget_usd"] = round(float(budget_usd), 3)
        for k, v in (("quiet_start", quiet_start), ("quiet_end", quiet_end)):
            if v is not None:
                if not 0 <= v <= 23:
                    raise ValueError("A hora deve ficar entre 0 e 23.")
                cur[k] = int(v)
        with self.engine.begin() as c:
            c.execute(self.prefs.delete().where(self.prefs.c.user_id == user_id))
            c.execute(self.prefs.insert().values(user_id=user_id, **cur))
        return cur

    # --- gasto ---
    def spent_today(self, user_id: str, day: str) -> float:
        with self.engine.connect() as c:
            r = c.execute(self.spend.select().where((self.spend.c.user_id == user_id) & (self.spend.c.day == day))).first()
        return float(r.usd) if r else 0.0

    def charge(self, user_id: str, day: str, usd: float) -> float:
        total = self.spent_today(user_id, day) + max(0.0, usd)
        with self.engine.begin() as c:
            c.execute(self.spend.delete().where((self.spend.c.user_id == user_id) & (self.spend.c.day == day)))
            c.execute(self.spend.insert().values(user_id=user_id, day=day, usd=total))
        return total

    # --- assuntos ---
    def list_topics(self, user_id: str) -> list[dict]:
        with self.engine.connect() as c:
            rows = c.execute(self.topics.select().where(self.topics.c.user_id == user_id).order_by(self.topics.c.created_at)).fetchall()
            gcount = {r.topic_id: r.n for r in c.execute(
                select(self.guides.c.topic_id, func.count().label("n")).where(self.guides.c.user_id == user_id).group_by(self.guides.c.topic_id))}
        return [self._topic(r, gcount.get(r.id, 0)) for r in rows]

    @staticmethod
    def _topic(r, guides: int = 0) -> dict:
        return {"id": r.id, "title": r.title, "status": r.status, "level": r.level, "level_label": level_label(r.level),
                "source": r.source, "guides": guides, "last_studied_at": r.last_studied_at.isoformat() if r.last_studied_at else None,
                "last_error": r.last_error}

    def get_topic(self, user_id: str, topic_id: str) -> Optional[dict]:
        with self.engine.connect() as c:
            r = c.execute(self.topics.select().where((self.topics.c.id == topic_id) & (self.topics.c.user_id == user_id))).first()
        return self._topic(r) if r else None

    def add_topic(self, user_id: str, title: str, source: str = "manual") -> dict:
        self._check(user_id)
        clean = " ".join((title or "").split()).strip(" .,;:!?")
        if not 3 <= len(clean) <= 80 or not re.search(r"[A-Za-zÀ-ÿ]{3}", clean):
            raise ValueError("Escreva o assunto em poucas palavras (de 3 a 80 letras).")
        if has_secret(clean) or (source != "manual" and sensitivity_for("outro", clean)):
            raise ValueError("Esse assunto é delicado demais para eu escolher sozinho.")
        norm = _norm(clean)
        existing = self.list_topics(user_id)
        if any(_norm(t["title"]) == norm for t in existing):
            raise ValueError("Esse assunto já está na lista.")
        if sum(1 for t in existing if t["status"] == "active") >= MAX_ACTIVE_TOPICS:
            raise ValueError(f"Já estou estudando {MAX_ACTIVE_TOPICS} assuntos. Pause ou apague um para incluir outro.")
        tid = uuid.uuid4().hex
        with self.engine.begin() as c:
            c.execute(self.topics.insert().values(id=tid, user_id=user_id, title=clean, norm=norm, status="active", level=0,
                                                  source=source if source in ("memoria", "curiosidade", "manual") else "manual",
                                                  created_at=_now(), last_studied_at=None, last_error=None))
        return self.get_topic(user_id, tid)  # type: ignore[return-value]

    def set_status(self, user_id: str, topic_id: str, status: str) -> Optional[dict]:
        if status not in ("active", "paused"):
            raise ValueError("estado invalido")
        if status == "active":
            topic = self.get_topic(user_id, topic_id)
            if topic and topic["status"] != "active" and sum(1 for t in self.list_topics(user_id) if t["status"] == "active") >= MAX_ACTIVE_TOPICS:
                raise ValueError(f"Já estou estudando {MAX_ACTIVE_TOPICS} assuntos. Pause um antes.")
        with self.engine.begin() as c:
            n = c.execute(self.topics.update().where((self.topics.c.id == topic_id) & (self.topics.c.user_id == user_id)).values(status=status)).rowcount
        return self.get_topic(user_id, topic_id) if n else None

    def delete_topic(self, user_id: str, topic_id: str) -> bool:
        with self.engine.begin() as c:
            n = c.execute(self.topics.delete().where((self.topics.c.id == topic_id) & (self.topics.c.user_id == user_id))).rowcount
            c.execute(self.guides.delete().where((self.guides.c.topic_id == topic_id) & (self.guides.c.user_id == user_id)))
            c.execute(self.sources.delete().where((self.sources.c.topic_id == topic_id) & (self.sources.c.user_id == user_id)))
        return bool(n)

    def forget_all(self, user_id: str) -> int:
        with self.engine.begin() as c:
            n = c.execute(self.topics.delete().where(self.topics.c.user_id == user_id)).rowcount or 0
            c.execute(self.guides.delete().where(self.guides.c.user_id == user_id))
            c.execute(self.sources.delete().where(self.sources.c.user_id == user_id))
        return n

    def mark(self, user_id: str, topic_id: str, *, level: Optional[int] = None, error: Optional[str] = None) -> None:
        vals: dict = {"last_error": error}
        if error is None:
            vals["last_studied_at"] = _now()
        if level is not None:
            vals["level"] = level
        with self.engine.begin() as c:
            c.execute(self.topics.update().where((self.topics.c.id == topic_id) & (self.topics.c.user_id == user_id)).values(**vals))

    # --- fontes que a pessoa indica (links para pesquisar) ---
    def add_source(self, user_id: str, url: str, topic_id: Optional[str] = None, title: str = "") -> dict:
        self._check(user_id)
        clean = clean_source_url(url)
        if clean is None:
            raise ValueError("Esse link não serve. Use um endereço de site que comece com http:// ou https://, como https://pt.wikipedia.org/…")
        if topic_id is not None and self.get_topic(user_id, topic_id) is None:
            raise ValueError("Não encontrei esse assunto.")
        with self.engine.connect() as c:
            dup = c.execute(self.sources.select().where((self.sources.c.user_id == user_id) & (self.sources.c.url == clean)
                                                        & (self.sources.c.topic_id == topic_id))).first()
            n = c.execute(select(func.count()).select_from(self.sources).where(self.sources.c.user_id == user_id)).scalar() or 0
        if dup is not None:
            return self._source(dup)
        if n >= MAX_SOURCES:
            raise ValueError(f"Você já indicou {MAX_SOURCES} fontes. Apague alguma para incluir outra.")
        sid = uuid.uuid4().hex
        label = " ".join((title or "").split())[:160] or site_domain(clean)
        with self.engine.begin() as c:
            c.execute(self.sources.insert().values(id=sid, user_id=user_id, topic_id=topic_id, url=clean, title=label, created_at=_now()))
        return {"id": sid, "topic_id": topic_id, "url": clean, "title": label}

    @staticmethod
    def _source(r) -> dict:
        return {"id": r.id, "topic_id": r.topic_id, "url": r.url, "title": r.title}

    def list_sources(self, user_id: str, topic_id: Optional[str] = None) -> list[dict]:
        q = self.sources.select().where(self.sources.c.user_id == user_id)
        if topic_id is not None:
            q = q.where(self.sources.c.topic_id == topic_id)
        with self.engine.connect() as c:
            return [self._source(r) for r in c.execute(q.order_by(self.sources.c.created_at.desc())).fetchall()]

    def delete_source(self, user_id: str, source_id: str) -> bool:
        with self.engine.begin() as c:
            return bool(c.execute(self.sources.delete().where((self.sources.c.id == source_id) & (self.sources.c.user_id == user_id))).rowcount)

    # --- guias ---
    def add_guide(self, user_id: str, topic_id: str, title: str, summary: str, body: str, sources: list[dict], level: int) -> str:
        gid = uuid.uuid4().hex
        with self.engine.begin() as c:
            c.execute(self.guides.insert().values(id=gid, topic_id=topic_id, user_id=user_id, title=title[:120], summary=summary, body=body,
                                                  sources=sources, level=level, created_at=_now()))
        return gid

    def latest_guide(self, user_id: str, topic_id: str) -> Optional[dict]:
        with self.engine.connect() as c:
            r = c.execute(self.guides.select().where((self.guides.c.topic_id == topic_id) & (self.guides.c.user_id == user_id))
                          .order_by(self.guides.c.created_at.desc())).first()
        return self._guide(r) if r else None

    def read_urls(self, user_id: str, topic_id: str) -> set[str]:
        with self.engine.connect() as c:
            rows = c.execute(self.guides.select().where((self.guides.c.topic_id == topic_id) & (self.guides.c.user_id == user_id))).fetchall()
        return {s.get("url", "") for r in rows for s in (r.sources or [])}

    def all_guides(self, user_id: str) -> list[dict]:
        with self.engine.connect() as c:
            rows = c.execute(self.guides.select().where(self.guides.c.user_id == user_id).order_by(self.guides.c.created_at.desc())).fetchall()
        return [self._guide(r) for r in rows]

    @staticmethod
    def _guide(r) -> dict:
        return {"id": r.id, "topic_id": r.topic_id, "title": r.title, "summary": r.summary, "body": r.body, "sources": r.sources or [],
                "level": r.level, "level_label": level_label(r.level), "created_at": r.created_at.isoformat()}


# ---------------- escolha de assuntos (memoria e curiosidade) ----------------
