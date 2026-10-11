"""Skill: olhar a tela da pessoa e explicar em linguagem simples (so com a aprovacao dela; a imagem nao fica guardada)."""
from __future__ import annotations

from src.jefrey.application.vision import look
from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool


class VisionSkill(SkillBase):
    metadata = SkillMetadata(
        name="vision", description="Olhar a tela do computador e explicar o que aparece (ajuda a entender mensagens, erros e sites)",
        tags=["visao", "ajuda"], requires_auth=False, enabled_by_default=True,
    )

    def initialize(self) -> bool:
        return True

    def get_tools(self) -> list:
        return [self.screen_look]

    @tool(description="Tira uma foto da tela do computador e responde sobre ela. question = o que a pessoa quer entender (ex.: 'o que esta escrito aqui?', 'o que esse erro quer dizer?'). Use quando a pessoa disser 'olha aqui', 'o que e isso na tela', 'nao entendi esse aviso'")
    async def screen_look(self, question: str = "", user_id: str | None = None) -> str:
        if not user_id or user_id in ("system", "anonymous"):
            return "Preciso saber quem você é."
        return (await look(user_id, question))["message"]


@skill("vision", "Ver a tela", tags=["visao", "ajuda"])
class _VisionWrapper(VisionSkill):
    pass
