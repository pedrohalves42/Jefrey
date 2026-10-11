"""Tarefas e contatos: tipos e regras puras (sem rede nem banco)."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


def plain(s: str) -> str:
    return re.sub(r"\s+", " ", "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")).strip()


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    due: str = ""  # AAAA-MM-DD ou vazio
    done: bool = False


@dataclass(frozen=True)
class Contact:
    name: str
    phones: tuple[str, ...] = field(default_factory=tuple)
    emails: tuple[str, ...] = field(default_factory=tuple)


def clean_title(title: str, limit: int = 200) -> str:
    return " ".join((title or "").split())[:limit]


def pick_task(tasks: list[Task], query: str) -> Task | None:
    """A tarefa aberta que a pessoa quis dizer: titulo igual, ou so uma que contenha o que ela falou. Ambiguo = None."""
    q = plain(query)
    if not q:
        return None
    open_ = [t for t in tasks if not t.done]
    exact = [t for t in open_ if plain(t.title) == q]
    if len(exact) == 1:
        return exact[0]
    partial = [t for t in open_ if q in plain(t.title)]
    return partial[0] if len(partial) == 1 else None


def match_contacts(contacts: list[Contact], query: str, limit: int = 5) -> list[Contact]:
    """Contatos cujo nome contem TODAS as palavras buscadas (sem acento nem maiuscula). Nome exato primeiro."""
    words = plain(query).split()
    if not words:
        return []
    hits = [c for c in contacts if all(w in plain(c.name) for w in words)]
    hits.sort(key=lambda c: (plain(c.name) != " ".join(words), plain(c.name)))
    return hits[:limit]
