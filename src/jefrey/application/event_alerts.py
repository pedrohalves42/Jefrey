"""Caso de uso: avisar a pessoa uns 15 minutos antes de cada compromisso da agenda."""
from __future__ import annotations

import logging
from datetime import timedelta

from src.jefrey.domain.event_alerts import LEAD, alert_text, due_alerts
from src.jefrey.ports import CalendarPort, ClockPort, NotifierPort, UserDirectoryPort

logger = logging.getLogger(__name__)
LOOKAHEAD = LEAD + timedelta(minutes=5)
MAX_REMEMBERED = 2000


class EventAlertService:
    def __init__(self, calendar: CalendarPort, notifier: NotifierPort, users: UserDirectoryPort, clock: ClockPort):
        self._calendar, self._notifier, self._users, self._clock = calendar, notifier, users, clock
        self._warned: set[str] = set()

    async def tick(self) -> list[str]:
        """Roda de tempos em tempos. Devolve os ids avisados agora. Uma falha de uma pessoa nunca atrapalha as outras."""
        sent: list[str] = []
        now = self._clock.now()
        for uid in self._users.known_users():
            try:
                events = await self._calendar.upcoming(uid, LOOKAHEAD)
            except Exception as e:
                logger.info("aviso de compromissos: agenda indisponivel (%s)", type(e).__name__)
                continue
            already = {w.split("|", 1)[1] for w in self._warned if w.startswith(f"{uid}|")}
            for ev in due_alerts(events, now, already):
                title, text = alert_text(ev, now)
                if self._notifier.notify(uid, title, text, urgent=True):
                    self._warned.add(f"{uid}|{ev.id}")
                    sent.append(ev.id)
        if len(self._warned) > MAX_REMEMBERED:
            self._warned.clear()
        return sent
