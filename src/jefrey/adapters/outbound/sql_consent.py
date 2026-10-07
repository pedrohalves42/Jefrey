"""Aceite dos termos e textos legais empacotados com o programa."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.jefrey.domain.privacy import TERMS_VERSION, strip_review_comments


class ConsentStore:
    """Aceite dos termos e da politica de privacidade (por pessoa e por versao). Fica mesmo apos "apagar tudo"."""

    def __init__(self):
        from sqlalchemy import Column, DateTime, String, Table

        from src.jefrey.core.db import Base, get_engine

        t = Base.metadata.tables.get("consents")
        if t is None:
            t = Table("consents", Base.metadata, Column("user_id", String(255), primary_key=True), Column("version", String(20), primary_key=True),
                      Column("accepted_at", DateTime, nullable=False))
        self.t, self.engine = t, get_engine()
        self.t.create(self.engine, checkfirst=True)

    def accepted(self, user_id: str, version: str = TERMS_VERSION) -> bool:
        with self.engine.connect() as c:
            return c.execute(self.t.select().where((self.t.c.user_id == user_id) & (self.t.c.version == version))).first() is not None

    def accept(self, user_id: str, version: str = TERMS_VERSION) -> None:
        if not user_id or user_id in ("system", "anonymous"):
            raise ValueError("usuario invalido")
        if self.accepted(user_id, version):
            return
        with self.engine.begin() as c:
            c.execute(self.t.insert().values(user_id=user_id, version=version, accepted_at=datetime.now(timezone.utc).replace(tzinfo=None)))


def documents() -> dict:
    """Textos legais empacotados com o programa (sem os comentarios internos de revisao)."""
    base = Path(__file__).resolve().parents[2] / "legal"
    out = {"version": TERMS_VERSION}
    for key, name in (("termos", "termos.md"), ("privacidade", "privacidade.md")):
        out[key] = strip_review_comments((base / name).read_text(encoding="utf-8"))
    return out
