"""Perfil da pessoa: como ela quer ser chamada. Isolado por usuario, em SQLite/Postgres."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional

MAX_NAME = 40
_PARTICLES = {"da", "de", "do", "das", "dos", "e"}
_NOT_NAMES = {"nao", "sim", "ok", "aqui", "ai", "tudo", "bem", "isso", "um", "uma", "o", "a", "meu", "minha", "voce", "vc",
              "jefrey", "assistente", "usuario", "user", "teste", "ninguem", "alguem"}
_WORD = r"[A-Za-zÀ-ÖØ-öø-ÿ'’]{1,20}"
_NAME_RE = re.compile(
    rf"(?:\bmeu nome (?:é|e|eh)\b|\bme chamo\b|\bpode me chamar de\b|\bme chama de\b|\bme chame de\b|\bmeu apelido (?:é|e)\b)\s+"
    rf"({_WORD}(?:\s+(?:da|de|do|das|dos|e)?\s*{_WORD}){{0,2}})(?![A-Za-zÀ-ÖØ-öø-ÿ'’])", re.IGNORECASE)


def _norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def _cap(word: str) -> str:
    """'d'ávila' -> "D'Ávila" (maiuscula no inicio e depois de apostrofo)."""
    return re.sub(r"(^|['’])([a-zà-ÿ])", lambda m: m.group(1) + m.group(2).upper(), word.lower())


def clean_name(raw: str) -> Optional[str]:
    """Nome apresentavel ('pedro da silva' -> 'Pedro da Silva') ou None se nao parecer um nome."""
    name = " ".join((raw or "").replace("’", "'").split())[:MAX_NAME * 2]
    if not name or len(name) > MAX_NAME or not re.fullmatch(rf"{_WORD}(?:\s+{_WORD}){{0,3}}", name):
        return None
    words = name.split()
    if _norm(words[0]) in _NOT_NAMES or all(_norm(w) in _NOT_NAMES | _PARTICLES for w in words):
        return None
    return " ".join(w.lower() if _norm(w) in _PARTICLES and i else _cap(w) for i, w in enumerate(words))


def detect_name(text: str) -> Optional[str]:
    """'meu nome é pedro, tudo bem?' -> 'Pedro'. So frases explicitas; nunca adivinha."""
    m = _NAME_RE.search(text or "")
    if not m:
        return None
    cand = m.group(1)
    for stop in (" e eu ", " e eh ", " e sou ", " e moro ", " e tenho ", " e gosto "):  # corta 'meu nome e Ana e eu moro...'
        idx = cand.lower().find(stop)
        if idx > 0:
            cand = cand[:idx]
    words = cand.split()
    while words and _norm(words[-1]) in _PARTICLES:
        words.pop()
    return clean_name(" ".join(words))


def _table():
    from sqlalchemy import Column, DateTime, String, Table

    from src.jefrey.core.db import Base

    t = Base.metadata.tables.get("user_profile")
    if t is not None:
        return t
    return Table("user_profile", Base.metadata,
                 Column("user_id", String(255), primary_key=True),
                 Column("display_name", String(80), nullable=True),
                 Column("updated_at", DateTime, nullable=False))


class ProfileStore:
    def __init__(self):
        from src.jefrey.core.db import get_engine

        self.t = _table()
        self.engine = get_engine()
        self.t.create(self.engine, checkfirst=True)

    def get_name(self, user_id: str) -> Optional[str]:
        with self.engine.connect() as c:
            row = c.execute(self.t.select().where(self.t.c.user_id == user_id)).first()
        return row.display_name if row and row.display_name else None

    def set_name(self, user_id: str, name: str) -> str:
        if not user_id or user_id in ("system", "anonymous"):
            raise ValueError("usuario invalido")
        clean = clean_name(name)
        if clean is None:
            raise ValueError("Esse nome não parece válido. Use só letras (até 40).")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self.engine.begin() as c:
            if c.execute(self.t.select().where(self.t.c.user_id == user_id)).first():
                c.execute(self.t.update().where(self.t.c.user_id == user_id).values(display_name=clean, updated_at=now))
            else:
                c.execute(self.t.insert().values(user_id=user_id, display_name=clean, updated_at=now))
        return clean

    def clear_name(self, user_id: str) -> None:
        with self.engine.begin() as c:
            c.execute(self.t.delete().where(self.t.c.user_id == user_id))
