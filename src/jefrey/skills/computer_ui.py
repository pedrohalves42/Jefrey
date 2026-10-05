"""Skill: operar OUTROS programas pelo teclado (focar janela, digitar texto, atalhos). Tudo exige a aprovacao da pessoa.

Seguranca (ver core/uiautomation.py): so age na janela confirmada, nunca em janelas protegidas, texto vira so letras, atalhos de lista fechada.
Estas ferramentas so sao oferecidas ao modelo quando a PESSOA pede (palavras como "digita", "atalho"): texto de e-mail, site ou
documento nunca as liga.
"""
from __future__ import annotations

import logging
import sys

from src.jefrey.core import uiautomation as UA
from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool

logger = logging.getLogger(__name__)


def _windows_only() -> str | None:
    return None if sys.platform == "win32" else "Isso só funciona no Windows."


class ComputerUISkill(SkillBase):
    metadata = SkillMetadata(
        name="computer_ui",
        description="Digitar e usar atalhos em outros programas, com a sua aprovação",
        tags=["utility", "local", "windows"],
        enabled_by_default=True,
    )

    def initialize(self) -> bool:
        return sys.platform == "win32"

    def get_tools(self) -> list:
        return [self.focus_window, self.type_text, self.press_hotkey]

    @tool(description="Traz uma janela aberta para a frente pelo nome do programa (ex.: Excel, Bloco de Notas). Pede aprovacao")
    async def focus_window(self, name: str, user_id: str | None = None) -> str:
        if (msg := _windows_only()):
            return msg
        try:
            hwnd = UA.focus(name)
        except UA.UIError as e:
            return str(e)
        return f"Trouxe para a frente: {UA.last_window_title(hwnd) or name}."

    @tool(description="Digita um texto em um programa aberto (ex.: window='Bloco de Notas', text='Olá'). Ate 500 letras. Pede aprovacao")
    async def type_text(self, text: str, window: str, user_id: str | None = None) -> str:
        if (msg := _windows_only()):
            return msg
        try:
            hwnd = UA.focus(window)
            UA.type_text(text, expect_hwnd=hwnd)
        except UA.UIError as e:
            return str(e)
        return f"Digitei {len(UA.clean_text(text))} letras em {UA.last_window_title(hwnd) or window}."

    @tool(description="Usa um atalho de teclado em um programa aberto: ctrl+c, ctrl+v, ctrl+x, ctrl+a, ctrl+s, ctrl+z, ctrl+y, ctrl+f, enter, esc, tab. Pede aprovacao")
    async def press_hotkey(self, combo: str, window: str, user_id: str | None = None) -> str:
        if (msg := _windows_only()):
            return msg
        try:
            hwnd = UA.focus(window)
            UA.hotkey(combo, expect_hwnd=hwnd)
        except UA.UIError as e:
            return str(e)
        return f"Usei o atalho {combo.lower().replace(' ', '')} em {UA.last_window_title(hwnd) or window}."


@skill("computer_ui", "Digitar e usar atalhos em outros programas, com a sua aprovação", tags=["utility", "local", "windows"])
class _ComputerUISkillWrapper(ComputerUISkill):
    pass
