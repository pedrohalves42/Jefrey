"""Skill: redes sociais. O Jefrey escreve carrosseis (com as imagens prontas) e posts; quem publica e a pessoa."""
from __future__ import annotations

from src.jefrey.application.social import make_carousel, make_post
from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool


def _need_user(user_id) -> bool:
    return not user_id or user_id in ("system", "anonymous")


class SocialSkill(SkillBase):
    metadata = SkillMetadata(
        name="social", description="Criar carrossel e posts para Instagram, Facebook, X e Telegram (o Jefrey escreve e desenha; voce publica)",
        tags=["social", "conteudo"], requires_auth=False, enabled_by_default=True,
    )

    def initialize(self) -> bool:
        return True

    def get_tools(self) -> list:
        return [self.social_carousel, self.social_post]

    @tool(description="Cria um carrossel para redes sociais sobre um assunto: escreve os slides e desenha as imagens prontas numa pasta. topic = assunto; slides = quantidade (3 a 10, padrao 6)")
    async def social_carousel(self, topic: str, slides: int = 6, user_id: str | None = None) -> str:
        if _need_user(user_id):
            return "Preciso saber quem você é."
        r = await make_carousel(user_id, topic, slides)
        if not r["ok"]:
            return r["message"]
        legenda = f"\nLegenda sugerida: {r['caption']} {' '.join(r['hashtags'])}".rstrip() if r["caption"] else ""
        return f"Carrossel “{r['title']}” pronto: {len(r['files'])} imagens na pasta {r['folder']}.{legenda}\nÉ só abrir a rede e publicar as imagens."

    @tool(description="Escreve um post para uma rede social. network = instagram, facebook, x ou telegram; topic = assunto. So escreve o texto, nao publica")
    async def social_post(self, network: str, topic: str, user_id: str | None = None) -> str:
        if _need_user(user_id):
            return "Preciso saber quem você é."
        r = await make_post(user_id, network, topic)
        return f"Rascunho para {r['network']}:\n{r['text']}" if r["ok"] else r["message"]


@skill("social", "Redes sociais", tags=["social", "conteudo"])
class _SocialWrapper(SocialSkill):
    pass
