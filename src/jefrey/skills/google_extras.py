"""Skills de Tarefas e Contatos do Google. So traduzem a chamada da ferramenta para os casos de uso (application/google_data)."""
from __future__ import annotations

from src.jefrey.adapters.outbound.google_rest import GoogleContactsAdapter, GoogleTasksAdapter
from src.jefrey.application.google_data import ContactService, TaskService
from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool


def _need_user(user_id) -> bool:
    return not user_id or user_id in ("system", "anonymous")


class GoogleTasksSkill(SkillBase):
    metadata = SkillMetadata(
        name="google_tasks", description="Tarefas do Google (listar, criar e marcar como feita)",
        tags=["google", "productivity"], requires_auth=True, enabled_by_default=True,
    )

    def __init__(self, service: TaskService | None = None):
        super().__init__()
        self._svc = service or TaskService(GoogleTasksAdapter())

    def initialize(self) -> bool:
        return True

    def get_tools(self) -> list:
        return [self.tasks_list, self.tasks_add, self.tasks_done]

    @tool(description="Lista as tarefas abertas do Google Tarefas da pessoa")
    async def tasks_list(self, user_id: str | None = None) -> str:
        return "Preciso saber quem você é." if _need_user(user_id) else await self._svc.list_open(user_id)

    @tool(description="Cria uma tarefa no Google Tarefas. title = o que fazer; due = data limite AAAA-MM-DD (opcional)")
    async def tasks_add(self, title: str, due: str = "", user_id: str | None = None) -> str:
        return "Preciso saber quem você é." if _need_user(user_id) else await self._svc.add(user_id, title, due)

    @tool(description="Marca uma tarefa aberta como feita. title = o nome da tarefa como esta na lista")
    async def tasks_done(self, title: str, user_id: str | None = None) -> str:
        return "Preciso saber quem você é." if _need_user(user_id) else await self._svc.complete(user_id, title)


class GoogleContactsSkill(SkillBase):
    metadata = SkillMetadata(
        name="google_contacts", description="Contatos do Google (achar telefone e e-mail de alguem)",
        tags=["google", "productivity"], requires_auth=True, enabled_by_default=True,
    )

    def __init__(self, service: ContactService | None = None):
        super().__init__()
        self._svc = service or ContactService(GoogleContactsAdapter())

    def initialize(self) -> bool:
        return True

    def get_tools(self) -> list:
        return [self.contacts_find]

    @tool(description="Procura um contato pelo nome e mostra telefone e e-mail. name = nome ou parte do nome")
    async def contacts_find(self, name: str, user_id: str | None = None) -> str:
        return "Preciso saber quem você é." if _need_user(user_id) else await self._svc.find(user_id, name)


@skill("google_tasks", "Tarefas do Google", tags=["google", "productivity"])
class _GoogleTasksWrapper(GoogleTasksSkill):
    pass


@skill("google_contacts", "Contatos do Google", tags=["google", "productivity"])
class _GoogleContactsWrapper(GoogleContactsSkill):
    pass
