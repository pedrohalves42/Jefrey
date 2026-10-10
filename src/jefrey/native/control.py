"""Ponto de contato entre o servidor e o lancador: pedir ao programa para fechar (botao Sair) ou mexer na janela."""
from __future__ import annotations

from typing import Callable, Optional

_quit: Optional[Callable[[], None]] = None
_show: Optional[Callable[[], None]] = None
_orb: Optional[Callable[[], None]] = None
_restart: Optional[Callable[[], None]] = None
_messages: Optional[Callable[[str], bool]] = None
_site: Optional[Callable[[str], bool]] = None
_site_counts: Optional[Callable[[], dict]] = None
_publish: Optional[Callable[..., dict]] = None


def set_restart_hook(fn: Optional[Callable[[], None]]) -> None:
    global _restart
    _restart = fn


def set_messages_hook(fn: Optional[Callable[[str], bool]]) -> None:
    global _messages
    _messages = fn


def set_site_hooks(open_fn: Optional[Callable[[str], bool]], counts_fn: Optional[Callable[[], dict]]) -> None:
    global _site, _site_counts
    _site, _site_counts = open_fn, counts_fn


def set_publish_hook(fn: Optional[Callable[..., dict]]) -> None:
    global _publish
    _publish = fn


def publish_in_site(net_id: str, text: str, files: list, send: bool) -> dict:
    """Publica pela janela da rede. {"ok", "message"}; sem janela propria (modo navegador) devolve ok=False."""
    if _publish is None:
        return {"ok": False, "message": "Publicar só funciona no programa instalado do Jefrey."}
    return _publish(net_id, text, files, send)


def open_site(net_id: str) -> bool:
    """Abre a janela de uma rede social (Instagram, Facebook, X, Telegram). So no programa nativo."""
    return bool(_site(net_id)) if _site is not None else False


def site_counts() -> dict:
    """{rede: novidades} das janelas ja abertas (pelo titulo da pagina)."""
    try:
        return dict(_site_counts()) if _site_counts is not None else {}
    except Exception:
        return {}


def open_messages(user_id: str) -> bool:
    """Abre o WhatsApp dentro do Jefrey para esta pessoa (so no programa nativo com janela propria)."""
    return bool(_messages(user_id)) if _messages is not None else False


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
