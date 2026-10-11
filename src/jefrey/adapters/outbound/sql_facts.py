"""Fatos aprendidos guardados no banco (SQLAlchemy), isolados por usuario. As regras estao em domain/learning.py."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from src.jefrey.domain.learning import *  # noqa: F401,F403
from src.jefrey.domain.learning import Fact, KINDS, MAX_ACTIVE, MAX_FACT, PROFILE_LIMIT, _clip, _norm, _plain, _validate, has_secret, sensitivity_for  # noqa: F401

def _tables():
    from sqlalchemy import Boolean, Column, DateTime, String, Table, Text

    from src.jefrey.core.db import Base

    facts = Base.metadata.tables.get("learned_facts")
    if facts is None:
        facts = Table("learned_facts", Base.metadata,
                      Column("id", String(40), primary_key=True),
                      Column("user_id", String(255), nullable=False, index=True),
                      Column("kind", String(20), nullable=False),
                      Column("fkey", String(80), nullable=False),
                      Column("text", Text, nullable=False),
                      Column("sensitive", Boolean, nullable=False, default=False),
                      Column("active", Boolean, nullable=False, default=True),
                      Column("created_at", DateTime, nullable=False),
                      Column("replaced_at", DateTime, nullable=True))
    prefs = Base.metadata.tables.get("learning_prefs")
    if prefs is None:
        prefs = Table("learning_prefs", Base.metadata,
                      Column("user_id", String(255), primary_key=True),
                      Column("enabled", Boolean, nullable=False, default=True))
    return facts, prefs


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class FactStore:
    def __init__(self):
        from src.jefrey.core.db import get_engine

        self.facts, self.prefs = _tables()
        self.engine = get_engine()
        self.facts.create(self.engine, checkfirst=True)
        self.prefs.create(self.engine, checkfirst=True)

    @staticmethod
    def _check(user_id: str) -> None:
        if not user_id or user_id in ("system", "anonymous"):
            raise ValueError("usuario invalido")

    # --- ligar/desligar ---
    def enabled(self, user_id: str) -> bool:
        with self.engine.connect() as c:
            row = c.execute(self.prefs.select().where(self.prefs.c.user_id == user_id)).first()
        return True if row is None else bool(row.enabled)

    def set_enabled(self, user_id: str, on: bool) -> None:
        self._check(user_id)
        with self.engine.begin() as c:
            if c.execute(self.prefs.select().where(self.prefs.c.user_id == user_id)).first():
                c.execute(self.prefs.update().where(self.prefs.c.user_id == user_id).values(enabled=on))
            else:
                c.execute(self.prefs.insert().values(user_id=user_id, enabled=on))

    # --- fatos ---
    def learn(self, user_id: str, fact: Fact) -> str:
        """'new' | 'same' | 'updated'. Mesma chave com texto novo substitui; o antigo vai para o historico."""
        self._check(user_id)
        t = self.facts
        with self.engine.begin() as c:
            cur = c.execute(t.select().where((t.c.user_id == user_id) & (t.c.kind == fact.kind) & (t.c.fkey == fact.key) & (t.c.active == True))).first()  # noqa: E712
            if cur is not None and _plain(cur.text) == _plain(fact.text):
                return "same"
            status = "new"
            if cur is not None:
                c.execute(t.update().where(t.c.id == cur.id).values(active=False, replaced_at=_now()))
                status = "updated"
            c.execute(t.insert().values(id=uuid.uuid4().hex, user_id=user_id, kind=fact.kind, fkey=fact.key, text=fact.text,
                                        sensitive=fact.sensitive, active=True, created_at=_now(), replaced_at=None))
            self._trim(c, user_id)
        return status

    def teach(self, user_id: str, text: str, kind: str = "outro") -> str:
        """A PESSOA ensina algo (mesmo caminho do aprendizado automatico, com as mesmas protecoes). 'new' | 'same' | 'updated'."""
        clean = _clip(text)
        if len(clean) < 3:
            raise ValueError("Escreva um pouco mais para eu guardar.")
        if has_secret(clean):
            raise ValueError("Isso parece uma senha ou um número de documento ou cartão. Isso eu não guardo.")
        kind = kind if kind in KINDS else "outro"
        return self.learn(user_id, Fact(kind, _plain(clean)[:60], clean, sensitivity_for(kind, clean)))

    def _trim(self, c, user_id: str) -> None:
        t = self.facts
        rows = c.execute(t.select().where((t.c.user_id == user_id) & (t.c.active == True)).order_by(t.c.created_at.desc())).fetchall()  # noqa: E712
        for r in rows[MAX_ACTIVE:]:
            c.execute(t.delete().where(t.c.id == r.id))

    def active(self, user_id: str, limit: int = 100) -> list[dict]:
        t = self.facts
        with self.engine.connect() as c:
            rows = c.execute(t.select().where((t.c.user_id == user_id) & (t.c.active == True)).order_by(t.c.created_at.desc()).limit(limit)).fetchall()  # noqa: E712
        return [self._row(r) for r in rows]

    def history(self, user_id: str, fkey: str) -> list[dict]:
        t = self.facts
        with self.engine.connect() as c:
            rows = c.execute(t.select().where((t.c.user_id == user_id) & (t.c.fkey == fkey)).order_by(t.c.created_at.desc())).fetchall()
        return [self._row(r) for r in rows]

    @staticmethod
    def _row(r) -> dict:
        return {"id": r.id, "kind": r.kind, "key": r.fkey, "text": r.text, "sensitive": bool(r.sensitive), "active": bool(r.active),
                "created_at": r.created_at.isoformat()}

    def correct(self, user_id: str, fact_id: str, text: str) -> Optional[dict]:
        """A pessoa corrige um fato (o texto novo tambem passa pelo filtro de segredos)."""
        clean = _validate([Fact("outro", "x", text)])
        if not clean:
            raise ValueError("Esse texto não pode ser guardado.")
        t = self.facts
        with self.engine.begin() as c:
            row = c.execute(t.select().where((t.c.id == fact_id) & (t.c.user_id == user_id))).first()
            if row is None:
                return None
            c.execute(t.update().where(t.c.id == fact_id).values(text=clean[0].text, sensitive=bool(row.sensitive) or clean[0].sensitive))
            row = c.execute(t.select().where(t.c.id == fact_id)).first()
        return self._row(row)

    def forget(self, user_id: str, fact_id: str) -> bool:
        """Apaga de verdade (o fato e o historico dele)."""
        t = self.facts
        with self.engine.begin() as c:
            row = c.execute(t.select().where((t.c.id == fact_id) & (t.c.user_id == user_id))).first()
            if row is None:
                return False
            c.execute(t.delete().where((t.c.user_id == user_id) & (t.c.fkey == row.fkey) & (t.c.kind == row.kind)))
        return True

    def forget_all(self, user_id: str) -> int:
        t = self.facts
        with self.engine.begin() as c:
            return c.execute(t.delete().where(t.c.user_id == user_id)).rowcount or 0

    def profile_lines(self, user_id: str, limit: int = PROFILE_LIMIT) -> list[str]:
        """Frases curtas para o prompt: so fatos ativos; saude e dinheiro ficam de fora (so quando a pessoa tocar no assunto)."""
        if not self.enabled(user_id):
            return []
        return [f["text"] for f in self.active(user_id, 200) if not f["sensitive"]][:limit]
