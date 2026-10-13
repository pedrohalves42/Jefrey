"""Atalho de compatibilidade do WhatsApp: regras em domain/whatsapp.py, casos de uso em application/whatsapp.py, banco em adapters/outbound/sql_whatsapp.py."""
from typing import Any, Optional

from src.jefrey.adapters.outbound.sql_whatsapp import WAStore, _hash, _now, _pairing, _tables  # noqa: F401
from src.jefrey.application import whatsapp as _app
from src.jefrey.application.whatsapp import compose_message, draft_reply  # noqa: F401
from src.jefrey.domain.whatsapp import *  # noqa: F401,F403
from src.jefrey.domain.whatsapp import _COMPOSE_SYSTEM, _SYSTEM  # noqa: F401


class SqlPersonContext:
    """O que o Jefrey sabe da pessoa para escrever no tom dela (nome e fatos), lido do banco."""

    def name(self, user_id: str) -> str:
        from src.jefrey.core.profile import ProfileStore

        return ProfileStore().get_name(user_id) or ""

    def known(self, user_id: str) -> list[str]:
        from src.jefrey.core.learning import FactStore

        return FactStore().profile_lines(user_id, 8)


async def handle_inbound(user_id: str, payload: dict, client: Any, *, store: Optional[WAStore] = None, who: Optional[SqlPersonContext] = None) -> dict:
    """Trata o que a extensao leu (ligacao padrao: banco SQL)."""
    return await _app.handle_inbound(user_id, payload, client, store=store or WAStore(), who=who or SqlPersonContext())
