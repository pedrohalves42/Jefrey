"""Quais skills estao realmente utilizaveis AGORA para um usuario (pre-requisitos atendidos).

O modelo so ve ferramentas utilizaveis: oferecer "enviar e-mail" sem conta Google conectada levava o
modelo a escolhe-la para qualquer pedido sobre e-mail e a pedir uma aprovacao sem sentido.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# skill -> provedor de login que ela exige
NEEDS_LOGIN = {"email": "google", "calendar": "google", "drive": "google", "google_tasks": "google", "google_contacts": "google"}


def connected_providers(user_id: str) -> set[str]:
    """Provedores em que o usuario fez login (hoje, so Google). Qualquer falha => nenhum (modo seguro)."""
    try:
        from src.jefrey.core.db import get_db
        from src.jefrey.core.models import OAuthToken

        with get_db() as session:
            rows = session.query(OAuthToken.provider).filter(OAuthToken.user_id == user_id).all()
        return {str(r[0]).split("_")[0] for r in rows}  # google, google_calendar -> google
    except Exception as e:
        logger.debug("connected_providers falhou (%s): assumindo nenhum", type(e).__name__)
        return set()


def unavailable_skills(user_id: str, connected: set[str] | None = None) -> dict[str, str]:
    """{skill: motivo} das skills sem pre-requisito. `connected` permite testar sem banco."""
    have = connected_providers(user_id) if connected is None else connected
    return {s: f"Conecte sua conta {p.capitalize()} para usar" for s, p in NEEDS_LOGIN.items() if p not in have}
