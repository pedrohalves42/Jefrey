"""Adaptadores de saida: ligam as portas ao mundo real (Google Agenda, balao do Windows, banco, relogio)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.jefrey.domain.event_alerts import UpcomingEvent


async def calendar_events(user_id: str, time_min: datetime, time_max: datetime, max_results: int = 10) -> list[dict]:
    """Eventos da agenda do Google ({id, summary, start}); `start` vem como texto ISO (ou AAAA-MM-DD em evento de dia inteiro).

    A skill expoe a ferramenta como StructuredTool: o jeito certo de chamar e `ainvoke` com um dicionario.
    """
    from src.jefrey.skills.calendar import CalendarSkill

    raw = await CalendarSkill().list_events.ainvoke(
        {"time_min": time_min.isoformat(), "time_max": time_max.isoformat(), "max_results": max_results, "user_id": user_id})
    if raw and isinstance(raw, list) and isinstance(raw[0], dict) and "error" in raw[0]:
        if any(k in str(raw[0].get("error", "")) for k in ("invalid_client", "invalid_grant", "unauthorized_client")):
            raise LookupError("google precisa de uma chave nova ou de um novo login")  # o painel mostra "conecte o Google"
        raise RuntimeError("agenda do Google indisponivel")
    return [e for e in (raw or []) if isinstance(e, dict)]


class GoogleCalendarAdapter:
    """CalendarPort sobre a skill do Google Agenda. Quem nao conectou o Google simplesmente nao tem eventos."""

    async def upcoming(self, user_id: str, within: timedelta) -> list[UpcomingEvent]:
        from src.jefrey.core import google_oauth as G

        if not G.status(user_id).get("connected"):
            return []
        now = datetime.now(timezone.utc)
        out: list[UpcomingEvent] = []
        for e in await calendar_events(user_id, now, now + within, 10):
            start = str(e.get("start") or "")  # evento de dia inteiro vem so com a data (AAAA-MM-DD): nao tem hora, nao avisa
            if "T" not in start:
                continue
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
