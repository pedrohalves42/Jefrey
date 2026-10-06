"""Adaptadores de saida: ligam as portas ao mundo real (Google Agenda, balao do Windows, banco, relogio)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.jefrey.domain.event_alerts import UpcomingEvent


class GoogleCalendarAdapter:
    """CalendarPort sobre a skill do Google Agenda. Quem nao conectou o Google simplesmente nao tem eventos."""

    async def upcoming(self, user_id: str, within: timedelta) -> list[UpcomingEvent]:
        from src.jefrey.core import google_oauth as G

        if not G.status(user_id).get("connected"):
            return []
        from src.jefrey.skills.calendar import CalendarSkill

        now = datetime.now(timezone.utc)
        raw = await CalendarSkill().list_events(time_min=now.isoformat(), time_max=(now + within).isoformat(), max_results=10, user_id=user_id)
        out: list[UpcomingEvent] = []
        for e in raw or []:
            start = str((e.get("start") or {}).get("dateTime", ""))  # eventos de dia inteiro nao tem hora: nao avisam
            try:
                when = datetime.fromisoformat(start.replace("Z", "+00:00"))
            except ValueError:
                continue
            if when.tzinfo is None:
                continue
            title = " ".join(str(e.get("summary") or "Compromisso").split())[:80]
            out.append(UpcomingEvent(id=str(e.get("id") or ""), title=title, starts_at=when))
        return out


class WindowsNotifier:
    """NotifierPort sobre o balao do icone da bandeja (core/notify)."""

    def notify(self, user_id: str, title: str, text: str, *, urgent: bool = False) -> bool:
        from src.jefrey.core import notify

        return notify.notify(user_id, title, text, urgent=urgent)


class DbUserDirectory:
    def known_users(self) -> list[str]:
        from src.jefrey.core.briefing import known_users

        return known_users()


class SystemClock:
    def now(self) -> datetime:
        from src.jefrey.core.reminders import local_tz

        return datetime.now(local_tz())
