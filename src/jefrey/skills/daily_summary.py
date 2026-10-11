"""Skill: resumo do dia (agenda, lembretes e clima) numa frase falada, montado por regras e sem chamar modelo de IA."""
from __future__ import annotations

from datetime import datetime

from src.jefrey.application.daily_summary import build_daily_summary
from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool


class DailySummarySkill(SkillBase):
    metadata = SkillMetadata(
        name="daily_summary", description="Resumo do dia: agenda, lembretes e clima",
        tags=["agenda", "hoje"], requires_auth=False, enabled_by_default=True,
    )

    def initialize(self) -> bool:
        return True

    def get_tools(self) -> list:
        return [self.daily_summary]

    @tool(description="Resumo do dia da pessoa: agenda, lembretes e clima em uma frase falada. Use para 'bom dia', 'o que eu tenho pra hoje', 'como esta o meu dia', 'resumo do dia'")
    async def daily_summary(self, user_id: str | None = None) -> str:
        if not user_id or user_id in ("system", "anonymous"):
            return "Preciso saber quem você é."
        from src.jefrey.core import today as T
        from src.jefrey.domain.reminders import local_tz
        from src.jefrey.ports.registry import use

        name = use("briefing_env").person_name(user_id)
        return await build_daily_summary(
            user_id=user_id, name=name, now=datetime.now(local_tz()),
            panel_loader=lambda uid: T.build(user_id=uid),
        )


@skill("daily_summary", "Resumo do dia", tags=["agenda", "hoje"])
class _DailySummaryWrapper(DailySummarySkill):
    pass
