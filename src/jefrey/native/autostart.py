"""Iniciar junto com o Windows (chave Run do usuario: nao precisa de administrador e a pessoa desliga quando quiser)."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE = "Jefrey"


def command() -> str | None:
    """So existe no programa instalado (Jefrey.exe): em desenvolvimento nao registra nada."""
    if not getattr(sys, "frozen", False):
        return None
    return f'"{Path(sys.executable).resolve()}" --minimized'


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, VALUE)
            return True
    except OSError:
        return False


def available() -> bool:
    return sys.platform == "win32" and command() is not None


def set_enabled(on: bool) -> bool:
    """True se ficou como pedido."""
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                cmd = command()
                if cmd is None:
                    return False
                winreg.SetValueEx(k, VALUE, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(k, VALUE)
                except FileNotFoundError:
                    pass
        return True
    except OSError as e:
        logger.info("nao consegui mudar o inicio automatico (%s)", type(e).__name__)
        return False
