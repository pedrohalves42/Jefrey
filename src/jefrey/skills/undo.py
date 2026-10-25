"""Skill: desfazer a ultima coisa que o Jefrey fez (lembrete criado, arquivo gravado). O que nao tem volta e dito com clareza."""
from __future__ import annotations

from pathlib import Path

from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool


def _undo_reminder(payload: dict) -> None:
    from src.jefrey.core.reminders import ReminderStore

    if not ReminderStore().cancel(payload["user_id"], payload["id"]):
        raise RuntimeError("lembrete nao encontrado")


def _undo_file(payload: dict) -> None:
    alvo = Path(payload["path"])
    if payload.get("previous") is None:
        alvo.unlink(missing_ok=True)
    else:
        alvo.write_text(payload["previous"], encoding="utf-8")


UNDOERS = {"delete_reminder": _undo_reminder, "restore_file": _undo_file}


class UndoSkill(SkillBase):
    metadata = SkillMetadata(
        name="undo", description="Desfazer a ultima coisa que o Jefrey fez (lembrete criado, arquivo gravado)",
        tags=["seguranca", "ajuda"], requires_auth=False, enabled_by_default=True,
    )

    def initialize(self) -> bool:
        return True

    def get_tools(self) -> list:
        return [self.undo_last]

    @tool(description="Desfaz a ultima coisa que voce fez para a pessoa (lembrete criado, arquivo gravado). Use quando ela disser 'desfaz isso', 'volta atras', 'cancela o que voce fez'. O que nao tem volta (mensagem enviada) e dito com clareza")
    async def undo_last(self, user_id: str | None = None) -> str:
        if not user_id or user_id in ("system", "anonymous"):
            return "Preciso saber quem você é."
        from src.jefrey.application.undo import shared_journal

        return shared_journal().undo_last(user_id, UNDOERS)


@skill("undo", "Desfazer", tags=["seguranca", "ajuda"])
class _UndoWrapper(UndoSkill):
    pass
