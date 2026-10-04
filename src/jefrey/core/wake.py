"""Sinal de "acorde": o atalho global do Windows pede para a tela comecar a ouvir.

A tela pergunta com frequencia (GET /system/wake); isso tambem diz ao programa que ha uma tela aberta (para decidir
entre trazer a janela para a frente ou abrir uma nova).
"""
from __future__ import annotations

import time
from typing import Optional

PENDING_TTL_S = 30.0
UI_ALIVE_S = 8.0
_pending: Optional[float] = None
_ui_seen: float = 0.0


def request(now: Optional[float] = None) -> None:
    global _pending
    _pending = time.monotonic() if now is None else now


def poll(now: Optional[float] = None) -> bool:
    """Chamado pela tela. True uma unica vez por pedido (se o pedido ainda e recente)."""
    global _pending, _ui_seen
    t = time.monotonic() if now is None else now
    _ui_seen = t
    if _pending is not None and t - _pending <= PENDING_TTL_S:
        _pending = None
        return True
    if _pending is not None and t - _pending > PENDING_TTL_S:
        _pending = None
    return False


def ui_alive(now: Optional[float] = None) -> bool:
    t = time.monotonic() if now is None else now
    return _ui_seen > 0 and t - _ui_seen <= UI_ALIVE_S


def reset() -> None:
    global _pending, _ui_seen
    _pending, _ui_seen = None, 0.0
