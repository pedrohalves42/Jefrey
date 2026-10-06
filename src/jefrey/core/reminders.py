"""Atalho de compatibilidade: a regra pura agora mora em domain/reminders.py e o banco em adapters/outbound/sql_reminders.py."""
import os
from datetime import datetime, timezone, tzinfo

from src.jefrey.adapters.outbound.sql_reminders import ReminderStore, _from_row, _model, _utc_naive  # noqa: F401
from src.jefrey.domain import reminders as _domain
from src.jefrey.domain.reminders import *  # noqa: F401,F403
from src.jefrey.domain.reminders import (  # noqa: F401
    DEFAULT_HOUR, MAX_PENDING, MAX_TEXT, PERIOD_HOUR, PT_WEEKDAYS, WEEKDAYS, ReminderRequest, When, _norm, describe_due, parse_request, parse_when,
)


def local_tz() -> tzinfo:
    name = os.getenv("JEFREY_TIMEZONE", "America/Sao_Paulo")
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        return datetime.now().astimezone().tzinfo or timezone.utc


_domain.set_tz_provider(local_tz)  # o fuso da pessoa vem do ambiente
