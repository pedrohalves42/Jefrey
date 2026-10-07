"""Ponto de contato entre o servidor e o lancador: pedir ao programa para fechar (botao Sair) ou mexer na janela."""
from __future__ import annotations

from typing import Callable, Optional

_quit: Optional[Callable[[], None]] = None
_show: Optional[Callable[[], None]] = None
_orb: Optional[Callable[[], None]] = None
_restart: Optional[Callable[[], None]] = None


def set_restart_hook(fn: Optional[Callable[[], None]]) -> None:
    global _restart
    _restart = fn


def can_restart() -> bool:
    return _restart is not None


def request_restart() -> bool:
    if _restart is None:
        return False
    _restart()
    return True


def set_quit_hook(fn: Optional[Callable[[], None]]) -> None:
    global _quit
    _quit = fn


def set_window_hooks(show: Optional[Callable[[], None]], orb: Optional[Callable[[], None]]) -> None:
    global _show, _orb
    _show, _orb = show, orb


def can_quit() -> bool:
    return _quit is not None


def has_window() -> bool:
    return _show is not None


def show_window() -> bool:
    if _show is None:
        return False
    _show()
    return True


def show_orb() -> bool:
    if _orb is None:
        return False
    _orb()
    return True


def request_quit() -> bool:
    """True se havia um lancador para atender o pedido (so existe no modo nativo)."""
    if _quit is None:
        return False
    _quit()
    return True
