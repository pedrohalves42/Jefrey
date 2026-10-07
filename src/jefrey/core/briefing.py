"""Atalho de compatibilidade do resumo do dia: regras em domain/briefing.py, casos de uso em application/briefing.py, banco em adapters/outbound/sql_briefing.py."""
from src.jefrey.adapters.outbound.sql_briefing import BriefingStore, _tables, known_users  # noqa: F401
from src.jefrey.application.briefing import _notified, _nudge_overdue, _nudged, briefing_tick, generate, reminder_tick  # noqa: F401
from src.jefrey.domain.briefing import *  # noqa: F401,F403
