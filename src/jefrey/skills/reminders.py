"""Skill: lembretes de verdade (guardados, com hora, entregues pelo app)."""
from __future__ import annotations

import logging

from src.jefrey.core.reminders import ReminderStore, describe_due, parse_when
from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool

logger = logging.getLogger(__name__)

ASK_WHEN = "Quando devo te lembrar? Diga, por exemplo: amanhã às 8h, daqui a 20 minutos ou todo dia às 8 da manhã."
REPEAT_LABEL = {"none": "", "daily": " (todo dia)", "weekly": " (toda semana)"}


def _need_user(user_id):
    return not user_id or user_id in ("system", "anonymous")


class RemindersSkill(SkillBase):
    metadata = SkillMetadata(
        name="reminders",
        description="Lembretes com hora (únicos ou repetidos), avisados pelo Jefrey",
        tags=["utility", "local"],
        enabled_by_default=True,
    )

    def initialize(self) -> bool:
        return True

    def get_tools(self) -> list:
        return [self.set_reminder, self.list_reminders, self.cancel_reminder]

    @tool(description="Cria um lembrete. text = o que lembrar; when = quando, em portugues (ex.: 'amanha as 8h', 'daqui a 20 minutos', 'todo dia as 8 da manha')")
    async def set_reminder(self, text: str, when: str = "", user_id: str | None = None) -> str:
        if _need_user(user_id):
            return "Preciso saber quem você é para guardar um lembrete."
        text = " ".join((text or "").split())
        if not text:
            return "O que devo te lembrar?"
        w = parse_when(when or "")
        if w.due is None:
            return ASK_WHEN
        try:
            r = ReminderStore().add(user_id, text, w.due, w.repeat)
        except ValueError as e:
            return f"Não consegui criar o lembrete: {e}."
        extra = " Assumi 9h; se quiser outro horário, é só me dizer." if w.assumed_time else ""
        return f"Pronto! Vou te lembrar de “{text}” {describe_due(w.due)}{REPEAT_LABEL[r['repeat']]}.{extra}"

    @tool(description="Lista os lembretes pendentes do usuario")
    async def list_reminders(self, user_id: str | None = None) -> str:
        if _need_user(user_id):
            return "Preciso saber quem você é para listar seus lembretes."
        items = ReminderStore().pending(user_id)
        if not items:
            return "Você não tem lembretes pendentes."
        lines = [f"- {i['text']} ({i['due_label']}){REPEAT_LABEL[i['repeat']]}" for i in items[:20]]
        more = f"\n(e mais {len(items) - 20})" if len(items) > 20 else ""
        return "Seus lembretes:\n" + "\n".join(lines) + more

    @tool(description="Cancela um lembrete pelo id")
    async def cancel_reminder(self, reminder_id: str, user_id: str | None = None) -> str:
        if _need_user(user_id):
            return "Preciso saber quem você é."
        return "Lembrete cancelado." if ReminderStore().cancel(user_id, reminder_id) else "Não encontrei esse lembrete."


@skill("reminders", "Lembretes com hora, avisados pelo Jefrey", tags=["utility", "local"])
class _RemindersSkillWrapper(RemindersSkill):
    pass
