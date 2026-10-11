"""Tarefas e Contatos do Google por HTTP direto (sem bibliotecas pesadas). O token vem de core.google_oauth e nunca sai daqui."""
from __future__ import annotations

import asyncio
from typing import Callable, Optional

import httpx

from src.jefrey.domain.google_data import Contact, Task

TASKS_URL = "https://tasks.googleapis.com/tasks/v1/lists/@default/tasks"
PEOPLE_URL = "https://people.googleapis.com/v1/people/me/connections"


def _token(user_id: str, service: str) -> str:
    from src.jefrey.core import google_oauth as G

    return G.access_token(user_id, service)


class _Base:
    def __init__(self, token_for: Optional[Callable[[str, str], str]] = None, transport: Optional[httpx.AsyncBaseTransport] = None):
        self._token_for = token_for or _token
        self._transport = transport

    async def _call(self, user_id: str, service: str, method: str, url: str, **kw) -> dict:
        token = await asyncio.to_thread(self._token_for, user_id, service)  # LookupError = nao conectado
        async with httpx.AsyncClient(timeout=15, transport=self._transport, follow_redirects=False) as c:
            r = await c.request(method, url, headers={"Authorization": f"Bearer {token}"}, **kw)
        if r.status_code in (401, 403):
            raise LookupError("sem permissao: conecte esse servico de novo")
        if r.status_code >= 400:
            raise RuntimeError(f"google {r.status_code}")
        return r.json() if r.content else {}


def _task(d: dict) -> Task:
    return Task(id=str(d.get("id", "")), title=str(d.get("title", ""))[:200], due=str(d.get("due", ""))[:10], done=d.get("status") == "completed")


class GoogleTasksAdapter(_Base):
    async def list_open(self, user_id: str, limit: int = 20) -> list[Task]:
        d = await self._call(user_id, "tasks", "GET", TASKS_URL, params={"showCompleted": "false", "maxResults": str(min(limit, 100))})
        return [t for t in (_task(i) for i in d.get("items", [])) if t.title and not t.done][:limit]

    async def add(self, user_id: str, title: str, due: str = "") -> Task:
        body: dict = {"title": title}
        if due:
            body["due"] = f"{due[:10]}T00:00:00.000Z"
        return _task(await self._call(user_id, "tasks", "POST", TASKS_URL, json=body))

    async def complete(self, user_id: str, task_id: str) -> bool:
        if not task_id or "/" in task_id:
            return False
        d = await self._call(user_id, "tasks", "PATCH", f"{TASKS_URL}/{task_id}", json={"status": "completed"})
        return d.get("status") == "completed"


    async def delete(self, user_id: str, task_id: str) -> bool:
        if not task_id or "/" in task_id:
            return False
        await self._call(user_id, "tasks", "DELETE", f"{TASKS_URL}/{task_id}")
        return True

    async def update(self, user_id: str, task_id: str, title: str = "", due: str = "") -> Task:
        if not task_id or "/" in task_id:
            raise ValueError("tarefa invalida")
        body: dict = {}
        if title:
            body["title"] = title
        if due:
            body["due"] = f"{due[:10]}T00:00:00.000Z"
        return _task(await self._call(user_id, "tasks", "PATCH", f"{TASKS_URL}/{task_id}", json=body))

    async def list_all(self, user_id: str, limit: int = 20) -> list[Task]:
        """As feitas recentes tambem (para 'o que eu fiz esta semana?')."""
        d = await self._call(user_id, "tasks", "GET", TASKS_URL, params={"showCompleted": "true", "showHidden": "true", "maxResults": str(min(limit, 100))})
        return [t for t in (_task(i) for i in d.get("items", [])) if t.title][:limit]


class GoogleContactsAdapter(_Base):
    async def all(self, user_id: str) -> list[Contact]:
        d = await self._call(user_id, "contacts", "GET", PEOPLE_URL, params={"personFields": "names,phoneNumbers,emailAddresses", "pageSize": "1000"})
        out: list[Contact] = []
        for p in d.get("connections", []):
            names = p.get("names") or []
            name = str((names[0] if names else {}).get("displayName", "")).strip()
            if not name:
                continue
            out.append(Contact(name=name[:80], phones=tuple(str(x.get("value", ""))[:30] for x in (p.get("phoneNumbers") or [])[:3] if x.get("value")),
                               emails=tuple(str(x.get("value", ""))[:80] for x in (p.get("emailAddresses") or [])[:2] if x.get("value"))))
        return out
