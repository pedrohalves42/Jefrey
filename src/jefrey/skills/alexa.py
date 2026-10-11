"""Skill: Alexa (falar nos Echo e acionar rotinas) via Voice Monkey. Ver core/alexa.py."""
from __future__ import annotations

from src.jefrey.core import alexa as A
from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool


class AlexaSkill(SkillBase):
    metadata = SkillMetadata(
        name="alexa",
        description="Fazer a Alexa falar um aviso e acionar rotinas da Alexa (via Voice Monkey)",
        tags=["home", "voice"],
        enabled_by_default=True,
    )

    def initialize(self) -> bool:
        return True

    def get_tools(self) -> list:
        return [self.alexa_say, self.alexa_routine, self.alexa_list]

    @tool(description="Faz a Alexa (Echo) falar uma mensagem curta em voz alta. 'device' e o nome do aparelho (ex.: sala); vazio usa o unico cadastrado; 'todos' fala na casa toda")
    async def alexa_say(self, text: str, device: str = "", user_id: str | None = None) -> str:
        try:
            return await A.say(text, device)
        except A.AlexaError as e:
            return str(e)

    @tool(description="Aciona uma rotina cadastrada da Alexa pelo nome (ex.: boa noite, luz da sala). Tem efeito real: pede aprovacao")
    async def alexa_routine(self, name: str, user_id: str | None = None) -> str:
        try:
            return await A.routine(name)
        except A.AlexaError as e:
            return str(e)

    @tool(description="Diz quais aparelhos e rotinas da Alexa estao cadastrados (use antes de falar ou acionar, se nao tiver certeza do nome)")
    async def alexa_list(self, user_id: str | None = None) -> str:
        return A.describe()


@skill("alexa", "Fazer a Alexa falar um aviso e acionar rotinas da Alexa (via Voice Monkey)", tags=["home", "voice"])
class _AlexaSkillWrapper(AlexaSkill):
    pass
