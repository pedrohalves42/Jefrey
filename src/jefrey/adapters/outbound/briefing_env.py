"""O que o resumo do dia e os avisos de lembrete usam do mundo de fora: lembretes, estudos, fatos, diario, perfil e o banco do resumo.
Imports na hora do uso (pelos nomes `core.*`), para os testes poderem trocar uma peca so."""
from __future__ import annotations

from typing import Any, Optional


class BriefingEnvironment:
    def store(self) -> Any:
        from src.jefrey.adapters.outbound.sql_briefing import BriefingStore

        return BriefingStore()

    def known_users(self) -> "list[str]":
        from src.jefrey.adapters.outbound.sql_briefing import known_users

        return known_users()

    def pending_reminders(self, user_id: str) -> list:
        from src.jefrey.core.reminders import ReminderStore

        return ReminderStore().pending(user_id)

    def due_reminders(self, user_id: str, now: Any) -> list:
        from src.jefrey.core.reminders import ReminderStore

        return ReminderStore().due(user_id, now)

    def guides(self, user_id: str) -> list:
        from src.jefrey.core.studies import StudyStore

        return StudyStore().all_guides(user_id)

    def fact_texts(self, user_id: str) -> "list[str]":
        from src.jefrey.core.learning import FactStore

        return [f["text"] for f in FactStore().active(user_id, 200)]

    def diary_day(self, user_id: str, day: str) -> Optional[str]:
        from src.jefrey.core.diary import DiaryStore

        return DiaryStore().get(user_id, day)

    def person_name(self, user_id: str) -> Optional[str]:
        from src.jefrey.core.profile import ProfileStore

        return ProfileStore().get_name(user_id)


def register() -> None:
    from src.jefrey.ports import registry

    registry.default("briefing_env", BriefingEnvironment)
