"""Skill: modo familia. Monta o resumo da semana para o cuidador (so contagens). Nunca envia: o envio e outra ferramenta, com aprovacao."""
from __future__ import annotations

from src.jefrey.domain.family import compose
from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool


class FamilySkill(SkillBase):
    metadata = SkillMetadata(
        name="family", description="Resumo semanal para a familia (so com consentimento)",
        tags=["familia", "seguranca"], requires_auth=False, enabled_by_default=True,
    )

    def initialize(self) -> bool:
        return True

    def get_tools(self) -> list:
        return [self.family_summary]

    @tool(description="Monta o resumo da semana para o familiar cuidador (so contagens, sem conversas). Use quando a pessoa pedir 'enviar resumo para a familia'. Nao envia nada: depois o envio pelo WhatsApp pede aprovacao")
    async def family_summary(self, user_id: str | None = None) -> str:
        if not user_id or user_id in ("system", "anonymous"):
            return "Preciso saber quem você é."
        from src.jefrey.application.family import shared_store
        from src.jefrey.core.reminders import ReminderStore
        from src.jefrey.ports.registry import use

        c = shared_store().get(user_id)
        if not c["enabled"]:
            return "O modo família está desligado. Você pode ligar em Configurações, escolhendo quem recebe."
        name = use("briefing_env").person_name(user_id)
        text = compose(name, c["contact"], len(ReminderStore().pending(user_id)))
        return f"Este é o resumo para {c['contact']}:\n{text}\nPosso enviar? Se disser sim, eu peço a sua aprovação antes."


@skill("family", "Resumo semanal para a familia", tags=["familia"])
class _FamilyWrapper(FamilySkill):
    pass
