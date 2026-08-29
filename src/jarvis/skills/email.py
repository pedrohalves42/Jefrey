"""Skill: E-mail (Gmail) - Placeholder."""
from __future__ import annotations
from typing import Any
import logging

from src.jarvis.skills import SkillBase, SkillMetadata, skill, tool

logger = logging.getLogger(__name__)


class EmailSkill(SkillBase):
    metadata = SkillMetadata(
        name="email",
        description="Gerencia Gmail (ler, enviar, organizar)",
        tags=["email", "gmail", "communication"],
        requires_auth=True,
    )
    
    def __init__(self):
        super().__init__()
        self._service = None
    
    async def initialize(self) -> bool:
        logger.info("Email skill: OAuth não implementado ainda")
        return False
    
    def get_tools(self) -> list:
        if not self._service:
            return []
        return [
            self.list_messages,
            self.get_message,
            self.send_message,
            self.reply_message,
            self.modify_labels,
            self.search_messages,
        ]
    
    @tool(description="Lista e-mails")
    async def list_messages(
        self,
        query: str | None = None,
        max_results: int = 20,
        label_ids: list[str] | None = None,
    ) -> list[dict]:
        return [{"message": "Email skill não configurada - precisa de OAuth"}]
    
    @tool(description="Lê e-mail completo")
    async def get_message(self, message_id: str) -> dict:
        return {"message": "Email skill não configurada - precisa de OAuth"}
    
    @tool(description="Envia e-mail")
    async def send_message(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
    ) -> dict:
        return {"message": "Email skill não configurada - precisa de OAuth"}
    
    @tool(description="Responde a um e-mail")
    async def reply_message(self, message_id: str, body: str) -> dict:
        return {"message": "Email skill não configurada - precisa de OAuth"}
    
    @tool(description="Modifica labels de e-mail")
    async def modify_labels(
        self,
        message_id: str,
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ) -> dict:
        return {"message": "Email skill não configurada - precisa de OAuth"}
    
    @tool(description="Busca avançada de e-mails")
    async def search_messages(self, query: str, max_results: int = 20) -> list[dict]:
        return [{"message": "Email skill não configurada - precisa de OAuth"}]


@skill("email", "Gmail integration", tags=["email", "gmail"], requires_auth=True)
class _EmailWrapper(EmailSkill):
    pass