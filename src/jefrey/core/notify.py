"""Avisos do Windows (balao perto do relogio), sem incomodar: poucos por dia e nunca de madrugada.

O lancador registra de que forma mostrar o aviso (icone da bandeja). Sem isso, nada e mostrado (a tela continua avisando).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger(__name__)

MAX_PER_DAY = 3  # avisos "simpaticos" (resumo, estudo); lembretes sao sempre entregues
QUIET_START, QUIET_END = 22, 7

_sink: Optional[Callable[[str, str], None]] = None
_count: dict[tuple[str, str], int] = {}


def set_sink(fn: Optional[Callable[[str, str], None]]) -> None:
    global _sink
    _sink = fn


def _quiet(now: datetime) -> bool:
    return now.hour >= QUIET_START or now.hour < QUIET_END


def notify(user_id: str, title: str, text: str, *, urgent: bool = False, now: Optional[datetime] = None) -> bool:
    """Mostra um aviso. `urgent` (lembrete) ignora o silencio e o limite do dia. Devolve se mostrou."""
    if _sink is None:
        return False
    if now is None:
        from src.jefrey.core.reminders import local_tz

        now = datetime.now(local_tz())
    key = (user_id, now.date().isoformat())
    if not urgent:
        if _quiet(now) or _count.get(key, 0) >= MAX_PER_DAY:
            return False
        _count[key] = _count.get(key, 0) + 1
        for k in [k for k in _count if k[1] != key[1]]:
            _count.pop(k, None)
    try:
        _sink(" ".join(title.split())[:60], " ".join(text.split())[:200])
        return True
    except Exception as e:
        logger.info("aviso do Windows indisponivel (%s)", type(e).__name__)
        return False
