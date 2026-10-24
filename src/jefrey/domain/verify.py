"""Acoes confirmadas (REGRAS PURAS): so afirma que algo ficou salvo se a releitura achou o resultado.

Depois de criar ou cancelar algo, o Jefrey LE de novo e passa o que achou. Se nao achou, diz com clareza que nao conseguiu confirmar.
"""
from __future__ import annotations

from typing import Mapping, Optional

NOT_CONFIRMED = "Não consegui confirmar que ficou salvo. Confira em Meus lembretes."


def confirm_created(ok_text: str, found: Optional[Mapping], expected_id: str) -> str:
    """`found` e o registro relido (ou None). So vale se for o MESMO registro que acabamos de criar."""
    if found and str(found.get("id")) == str(expected_id):
        return ok_text
    return NOT_CONFIRMED


def confirm_removed(ok_text: str, still_there: bool) -> str:
    return "Tentei cancelar, mas o lembrete ainda aparece. Tente de novo." if still_there else ok_text
