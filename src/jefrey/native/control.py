"""Ponto de contato entre o servidor e o lancador: pedir ao programa para fechar (botao Sair)."""
from __future__ import annotations

from typing import Callable, Optional

_quit: Optional[Callable[[], None]] = None


def set_quit_hook(fn: Optional[Callable[[], None]]) -> None:
    global _quit
    _quit = fn


def can_quit() -> bool:
    return _quit is not None


def request_quit() -> bool:
    """True se havia um lancador para atender o pedido (so existe no modo nativo)."""
    if _quit is None:
        return False
    _quit()
    return True
