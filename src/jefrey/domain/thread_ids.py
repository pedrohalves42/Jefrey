"""Identificadores de conversa isolados por usuario."""
from __future__ import annotations


def _ns_thread_id(thread_id: str, user_id: str | None) -> str:
    """Namespacing para isolamento multi-tenant (Axiom #2): `user_id:thread_id`.

    Conversas de usuarios diferentes nunca compartilham o mesmo identificador.
    Sem user_id devolve o thread_id original (compat).
    """
    if not user_id:
        return thread_id
    if thread_id.startswith(f"{user_id}:"):
        return thread_id
    return f"{user_id}:{thread_id}"
