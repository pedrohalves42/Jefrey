"""Casos de uso de Tarefas e Contatos do Google. Falam em portugues simples com a pessoa; nunca expoem erros tecnicos."""
from __future__ import annotations

import logging

from src.jefrey.domain.google_data import clean_title, match_contacts, pick_task
from src.jefrey.ports import ContactsPort, TasksPort

logger = logging.getLogger(__name__)
NOT_CONNECTED = "Para isso preciso do seu Google. Abra Conexões → Google e marque essa opção."


class TaskService:
    def __init__(self, tasks: TasksPort):
        self._tasks = tasks

    async def list_open(self, user_id: str) -> str:
        try:
            items = await self._tasks.list_open(user_id, 15)
        except LookupError:
            return NOT_CONNECTED
        except Exception as e:
            logger.info("tarefas: falhou (%s)", type(e).__name__)
            return "Não consegui ler suas tarefas agora."
        if not items:
            return "Você não tem tarefas abertas. 🎉"
        return "Suas tarefas abertas:\n" + "\n".join(f"- {t.title}" + (f" (até {t.due[8:10]}/{t.due[5:7]})" if t.due else "") for t in items)

    async def add(self, user_id: str, title: str, due: str = "") -> str:
        title = clean_title(title)
        if not title:
            return "Qual é a tarefa?"
        try:
            t = await self._tasks.add(user_id, title, due)
        except LookupError:
            return NOT_CONNECTED
        except Exception as e:
            logger.info("tarefas: nao criou (%s)", type(e).__name__)
            return "Não consegui criar a tarefa agora."
        return f"Anotado na sua lista de tarefas: “{t.title}”."

    async def complete(self, user_id: str, query: str) -> str:
        try:
            found = pick_task(await self._tasks.list_open(user_id, 50), query)
            if found is None:
                return "Não achei uma tarefa só com esse nome. Diga o nome do jeito que está na lista."
            ok = await self._tasks.complete(user_id, found.id)
        except LookupError:
            return NOT_CONNECTED
        except Exception as e:
            logger.info("tarefas: nao concluiu (%s)", type(e).__name__)
            return "Não consegui marcar como feita agora."
        return f"Pronto, marquei “{found.title}” como feita." if ok else "Não consegui marcar como feita agora."


    async def delete(self, user_id: str, query: str) -> str:
        try:
            found = pick_task(await self._tasks.list_open(user_id, 50), query)
            if found is None:
                return "Não achei uma tarefa só com esse nome. Diga o nome do jeito que está na lista."
            ok = await self._tasks.delete(user_id, found.id)
        except LookupError:
            return NOT_CONNECTED
        except Exception as e:
            logger.info("tarefas: nao apagou (%s)", type(e).__name__)
            return "Não consegui apagar a tarefa agora."
        return f"Pronto, apaguei “{found.title}”." if ok else "Não consegui apagar a tarefa agora."

    async def edit(self, user_id: str, query: str, new_title: str = "", due: str = "") -> str:
        new_title = clean_title(new_title) if new_title else ""
        if not new_title and not due:
            return "O que você quer mudar: o nome ou a data?"
        try:
            found = pick_task(await self._tasks.list_open(user_id, 50), query)
            if found is None:
                return "Não achei uma tarefa só com esse nome. Diga o nome do jeito que está na lista."
            t = await self._tasks.update(user_id, found.id, new_title, due)
        except LookupError:
            return NOT_CONNECTED
        except Exception as e:
            logger.info("tarefas: nao mudou (%s)", type(e).__name__)
            return "Não consegui mudar a tarefa agora."
        return f"Pronto, a tarefa agora é “{t.title}”" + (f", até {t.due[8:10]}/{t.due[5:7]}." if t.due else ".")

    async def recent(self, user_id: str) -> str:
        try:
            items = await self._tasks.list_all(user_id, 30)
        except LookupError:
            return NOT_CONNECTED
        except Exception as e:
            logger.info("tarefas: falhou (%s)", type(e).__name__)
            return "Não consegui ler suas tarefas agora."
        done = [t for t in items if t.done]
        if not done:
            return "Ainda não vi nenhuma tarefa feita."
        return "Tarefas que você já fez:\n" + "\n".join(f"- {t.title}" for t in done[:10])


class ContactService:
    def __init__(self, contacts: ContactsPort):
        self._contacts = contacts

    async def find(self, user_id: str, query: str) -> str:
        try:
            hits = match_contacts(await self._contacts.all(user_id), query)
        except LookupError:
            return NOT_CONNECTED
        except Exception as e:
            logger.info("contatos: falhou (%s)", type(e).__name__)
            return "Não consegui ler seus contatos agora."
        if not hits:
            return "Não achei esse contato."
        lines = []
        for c in hits:
            extra = ", ".join(list(c.phones[:2]) + list(c.emails[:1]))
            lines.append(f"- {c.name}" + (f": {extra}" if extra else ""))
        return "\n".join(lines)
