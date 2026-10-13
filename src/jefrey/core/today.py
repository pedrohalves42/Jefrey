"""Atalho de compatibilidade do painel "Hoje": regras em domain/today.py, casos de uso em application/today.py, fontes em adapters/outbound/today_sources.py."""
from typing import Optional

from src.jefrey.adapters.outbound import today_sources as _src
from src.jefrey.adapters.outbound.today_sources import (  # noqa: F401
    HttpPanelSources, _cache, _feed, _prefs_file, fetch_market, fetch_weather, load_prefs, save_interests, save_prefs,
)
from src.jefrey.adapters.outbound.today_sources import _agenda as _default_agenda, _reminders as _default_reminders
from src.jefrey.application import today as _app
from src.jefrey.application.today import _section  # noqa: F401
from src.jefrey.domain.today import *  # noqa: F401,F403
from src.jefrey.domain.today import _clean  # noqa: F401


async def _agenda(user_id: str) -> list[dict]:
    return await _default_agenda(user_id)


async def _reminders(user_id: str) -> list[dict]:
    return await _default_reminders(user_id)


async def build(*, user_id: str, transport=None) -> dict:
    """Monta o painel com as fontes publicas de verdade (``transport`` troca a rede em teste)."""
    return await _app.build(user_id=user_id, sources=HttpPanelSources(transport), prefs=load_prefs(), agenda=_agenda, reminders=_reminders)
