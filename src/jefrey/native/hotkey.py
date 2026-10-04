"""Atalho global do Windows (padrao Ctrl+Alt+J): chama o Jefrey de qualquer programa.

Sem dependencias: usa a API do Windows (RegisterHotKey) numa thread propria. Se o atalho ja estiver em uso por outro
programa, apenas nao registra (o Jefrey segue funcionando).
"""
from __future__ import annotations

import logging
import os
import sys
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

DEFAULT_HOTKEY = "ctrl+alt+j"
_MODS = {"alt": 0x0001, "ctrl": 0x0002, "control": 0x0002, "shift": 0x0004, "win": 0x0008}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012


def parse_hotkey(spec: str) -> Optional[tuple[int, int]]:
    """'ctrl+alt+j' -> (modificadores, codigo da tecla). None se invalido (precisa de ao menos um modificador e uma letra/numero)."""
    parts = [p.strip().lower() for p in (spec or "").split("+") if p.strip()]
    if len(parts) < 2:
        return None
    key = parts[-1]
    mods = 0
    for p in parts[:-1]:
        if p not in _MODS:
            return None
        mods |= _MODS[p]
    if not mods or len(key) != 1 or not key.isalnum() or not key.isascii():
        return None
    return mods, ord(key.upper())


def focus_window(title_part: str = "Jefrey") -> bool:
    """Traz para a frente a janela do navegador que mostra o Jefrey. False se nao achou ou nao e Windows."""
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found: list[int] = []
    EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if buf.value.startswith(title_part) or f"{title_part} - " in buf.value or f"- {title_part}" in buf.value:
                    found.append(hwnd)
        return True

    user32.EnumWindows(EnumProc(cb), 0)
    if not found:
        return False
    hwnd = found[0]
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.keybd_event(0x12, 0, 0, 0)  # Alt: o Windows so deixa trazer janela para a frente logo apos uma tecla
    user32.SetForegroundWindow(hwnd)
    user32.keybd_event(0x12, 0, 2, 0)
    return True


def start_hotkey(callback: Callable[[], None], spec: Optional[str] = None) -> Optional[Callable[[], None]]:
    """Registra o atalho. Devolve uma funcao que o desliga, ou None se nao deu (outro programa usa, nao e Windows)."""
    if sys.platform != "win32":
        return None
    parsed = parse_hotkey(spec or os.getenv("JEFREY_HOTKEY", DEFAULT_HOTKEY))
    if parsed is None:
        logger.warning("atalho invalido; use algo como ctrl+alt+j")
        return None
    mods, vk = parsed
    import ctypes
    from ctypes import wintypes

    ready = threading.Event()
    state: dict = {"ok": False, "tid": 0}

    def loop() -> None:
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        state["tid"] = kernel32.GetCurrentThreadId()
        if not user32.RegisterHotKey(None, 1, mods | MOD_NOREPEAT, vk):
            ready.set()
            return
        state["ok"] = True
        ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY:
                try:
                    callback()
                except Exception as e:  # nunca derruba a thread
                    logger.warning("atalho: acao falhou (%s)", type(e).__name__)
        user32.UnregisterHotKey(None, 1)

    t = threading.Thread(target=loop, daemon=True, name="jefrey-hotkey")
    t.start()
    ready.wait(3)
    if not state["ok"]:
        logger.warning("nao consegui registrar o atalho (outro programa pode estar usando)")
        return None

    def stop() -> None:
        try:
            ctypes.windll.user32.PostThreadMessageW(state["tid"], WM_QUIT, 0, 0)
        except Exception as _e:
            logger.debug("ignorado (%s): %s", 'hotkey.py', type(_e).__name__)

    return stop
