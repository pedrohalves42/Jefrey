"""Botao "Parar tudo": enquanto ativo, nenhuma ferramenta que mexe no computador executa.

Vale por poucos segundos (HALT_SECONDS) ou ate a pessoa fazer uma nova pergunta. E um interruptor de seguranca simples e global:
o Jefrey roda para uma pessoa so neste computador.
"""
from __future__ import annotations

import time

HALT_SECONDS = 30.0
# ferramentas que agem no computador (as de risco alto aprovadas ou nao: com a parada ligada, nenhuma roda)
COMPUTER_TOOLS = {"open_app", "open_folder", "open_website", "set_volume", "media_control", "search_in_browser",
                  "close_app", "focus_window", "type_text", "press_hotkey", "app_command"}

_until = 0.0


def _now() -> float:
    return time.monotonic()


def request_halt() -> None:
    global _until
    _until = _now() + HALT_SECONDS


def clear() -> None:
    global _until
    _until = 0.0


def is_halted() -> bool:
    return _now() < _until
