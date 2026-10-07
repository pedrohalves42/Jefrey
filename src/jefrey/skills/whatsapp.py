"""Skill: mandar mensagem de WhatsApp pelo pedido da pessoa (sempre com aprovacao mostrando o texto)."""
from __future__ import annotations

from src.jefrey.application.whatsapp_send import queue_for_contact
from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool


class WhatsAppSkill(SkillBase):
    metadata = SkillMetadata(
        name="whatsapp", description="Manda mensagem no WhatsApp (pelo WhatsApp Web no Chrome) para uma conversa que o Jefrey conhece",
        tags=["whatsapp", "mensagens"], requires_auth=False, enabled_by_default=True,
    )

    def __init__(self, store=None):
        super().__init__()
        self._store = store

    def initialize(self) -> bool:
        return True

    def get_tools(self) -> list:
        return [self.wa_send_message]

    @tool(description="Manda uma mensagem de WhatsApp. contact = nome da pessoa como aparece no WhatsApp; message = o texto EXATO a enviar (so o que a pessoa pediu; nunca invente)")
    async def wa_send_message(self, contact: str, message: str, user_id: str | None = None) -> str:
        if not user_id or user_id in ("system", "anonymous"):
            return "Preciso saber quem você é."
        store = self._store
        if store is None:
            from src.jefrey.adapters.outbound.sql_whatsapp import WAStore

            store = WAStore()
        return queue_for_contact(store, user_id, contact, message)


@skill("whatsapp", "Mandar mensagem de WhatsApp", tags=["whatsapp", "mensagens"])
class _WhatsAppWrapper(WhatsAppSkill):
    pass
