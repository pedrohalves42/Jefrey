"""Regras puras do aviso de compromissos: quais eventos merecem um aviso agora. Sem rede, sem banco, sem relogio proprio."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

LEAD = timedelta(minutes=15)  # avisa quando faltarem ate 15 minutos


@dataclass(frozen=True)
class UpcomingEvent:
    id: str
    title: str
    starts_at: datetime  # sempre com fuso


def due_alerts(events: list[UpcomingEvent], now: datetime, already: set[str], lead: timedelta = LEAD) -> list[UpcomingEvent]:
    """Eventos que comecam dentro de `lead` (e ainda nao comecaram) e que ainda nao foram avisados. Ordem de inicio."""
    out = [e for e in events if e.id and e.id not in already and now <= e.starts_at <= now + lead]
    return sorted(out, key=lambda e: e.starts_at)


def alert_text(ev: UpcomingEvent, now: datetime) -> tuple[str, str]:
    """(titulo, texto) curtos para o balao do Windows."""
    mins = max(1, round((ev.starts_at - now).total_seconds() / 60))
    when = "agora" if mins <= 1 else f"daqui a {mins} minutos"
    hhmm = ev.starts_at.astimezone(now.tzinfo).strftime("%H:%M") if now.tzinfo else ev.starts_at.strftime("%H:%M")
    return "Compromisso chegando", f"{ev.title} começa {when} (às {hhmm})."
