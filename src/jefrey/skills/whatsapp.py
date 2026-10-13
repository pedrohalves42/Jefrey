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
        return [self.wa_send_message, self.wa_inbox, self.wa_conversation]

    @tool(description="Manda uma mensagem de WhatsApp. contact = nome da pessoa como aparece no WhatsApp; message = o texto EXATO a enviar (so o que a pessoa pediu; nunca invente)")
    async def wa_send_message(self, contact: str, message: str, user_id: str | None = None) -> str:
        if not user_id or user_id in ("system", "anonymous"):
            return "Preciso saber quem você é."
        store = self._store
        if store is None:
            from src.jefrey.adapters.outbound.sql_whatsapp import WAStore

            store = WAStore()
        return queue_for_contact(store, user_id, contact, message)


    def _the_store(self):
        if self._store is not None:
            return self._store
        from src.jefrey.adapters.outbound.sql_whatsapp import WAStore

        return WAStore()

    @tool(description="Mostra quem mandou mensagem nova no WhatsApp (conversas com mensagens nao lidas e uma previa)")
    async def wa_inbox(self, user_id: str | None = None) -> str:
        if not user_id or user_id in ("system", "anonymous"):
            return "Preciso saber quem você é."
        from src.jefrey.application.whatsapp_inbox import unread_text

        return unread_text(self._the_store(), user_id)

    @tool(description="Le as ultimas mensagens de uma conversa do WhatsApp que o Jefrey ja viu. contact = nome como aparece no WhatsApp")
    async def wa_conversation(self, contact: str, user_id: str | None = None) -> str:
        if not user_id or user_id in ("system", "anonymous"):
            return "Preciso saber quem você é."
        from src.jefrey.application.whatsapp_inbox import history_text

        return history_text(self._the_store(), user_id, contact)


@skill("whatsapp", "Mandar mensagem de WhatsApp", tags=["whatsapp", "mensagens"])
class _WhatsAppWrapper(WhatsAppSkill):
    pass
