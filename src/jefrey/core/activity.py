"""O que a pessoa e o Jefrey estao fazendo agora (so em memoria).

- quando a pessoa usou o Jefrey pela ultima vez: o estudo em segundo plano so roda com ela ausente;
- o que o Jefrey faz sozinho neste momento ("estudando", "aprendendo"): a tela mostra no avatar.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

_started = time.monotonic()
_last: dict[str, float] = {}
_busy: dict[str, dict[str, int]] = {}
KINDS = ("estudando", "aprendendo")


def touch(user_id: str) -> None:
    if user_id and user_id not in ("system", "anonymous"):
        _last[user_id] = time.monotonic()


def idle_seconds(user_id: str) -> float:
    """Segundos desde a ultima mensagem; se nao houve nenhuma desde que o programa abriu, conta desde a abertura."""
    return time.monotonic() - _last.get(user_id, _started)


@contextmanager
def busy(user_id: str, kind: str, label: str = "") -> Iterator[None]:
    """Marca que o Jefrey esta fazendo algo em segundo plano (contagem, para tarefas que se sobrepoem)."""
    if kind not in KINDS or not user_id:
        yield
        return
    d = _busy.setdefault(user_id, {})
    d[kind] = d.get(kind, 0) + 1
    if label:
        _labels[(user_id, kind)] = label[:60]
    try:
        yield
    finally:
        d[kind] = max(0, d.get(kind, 1) - 1)
        if not d[kind]:
            _labels.pop((user_id, kind), None)


_labels: dict[tuple[str, str], str] = {}


def current(user_id: str) -> dict:
    d = _busy.get(user_id, {})
    return {"studying": d.get("estudando", 0) > 0, "learning": d.get("aprendendo", 0) > 0,
            "topic": _labels.get((user_id, "estudando"))}
