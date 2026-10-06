"""Portas (interfaces) que o nucleo do Jefrey precisa do mundo de fora. Quem implementa mora em `adapters/outbound`.

Regra da casa: `domain` e `application` so conhecem estas portas, nunca FastAPI, SQLAlchemy, httpx, Windows ou Google.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol

from src.jefrey.domain.event_alerts import UpcomingEvent
from src.jefrey.domain.google_data import Contact, Task
from src.jefrey.domain.learning import Fact


class CalendarPort(Protocol):
    async def upcoming(self, user_id: str, within: timedelta) -> list[UpcomingEvent]:
        """Compromissos que comecam nos proximos `within`. Lista vazia se a agenda nao esta conectada."""
        ...


class NotifierPort(Protocol):
    def notify(self, user_id: str, title: str, text: str, *, urgent: bool = False) -> bool:
        """Mostra um aviso para a pessoa. True se mostrou."""
        ...


class UserDirectoryPort(Protocol):
    def known_users(self) -> list[str]: ...


class ClockPort(Protocol):
    def now(self) -> datetime:
        """Agora, com fuso."""
        ...


class TasksPort(Protocol):
    async def list_open(self, user_id: str, limit: int = 20) -> "list[Task]": ...
    async def add(self, user_id: str, title: str, due: str = "") -> "Task": ...
    async def complete(self, user_id: str, task_id: str) -> bool: ...


class ContactsPort(Protocol):
    async def all(self, user_id: str) -> "list[Contact]": ...


class FactsPort(Protocol):
    """Fatos aprendidos da pessoa (quem implementa: adapters/outbound/sql_facts.py)."""

    def enabled(self, user_id: str) -> bool: ...
    def learn(self, user_id: str, fact: "Fact") -> str: ...


class WhatsAppStorePort(Protocol):
    """O que o tratamento de mensagens do WhatsApp precisa do armazenamento (quem implementa: adapters/outbound/sql_whatsapp.py)."""

    def touch_chat(self, user_id: str, name: str) -> dict: ...
    def paused(self, user_id: str) -> bool: ...
    def is_new(self, user_id: str, key: str) -> bool: ...
    def recent_drafts(self, user_id: str, chat_id: "str | None", seconds: int) -> int: ...
    def add_draft(self, user_id: str, chat: dict, incoming: str, reply: str, why: str, status: str, msg_ids: "list[str]") -> dict: ...


class PersonContextPort(Protocol):
    """Nome e fatos da pessoa, para escrever no jeito dela."""

    def name(self, user_id: str) -> str: ...
    def known(self, user_id: str) -> "list[str]": ...
