"""Perguntas simples sobre a agenda ("o que tenho hoje?") respondidas direto, sem gastar uma rodada do modelo de IA. Regra pura."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Optional

_DAY = r"(hoje|amanha)"
_ASK = [
    re.compile(rf"^(?:o que|oque)\s+(?:eu\s+)?tenho\s+(?:na|de|em)\s+(?:minha\s+)?agenda\s+(?:para\s+|pra\s+|de\s+)?{_DAY}$"),
    re.compile(rf"^(?:o que|oque)\s+(?:eu\s+)?tenho\s+(?:marcado|agendado|de compromissos?)\s+(?:para\s+|pra\s+|na\s+|no\s+)?{_DAY}$"),
    re.compile(rf"^(?:qual|quais)\s+(?:e\s+|sao\s+)?(?:a\s+|os\s+)?(?:minha\s+|meus\s+)?(?:agenda|compromissos)\s+(?:de\s+|para\s+|pra\s+)?{_DAY}$"),
    re.compile(rf"^(?:minha\s+)?agenda\s+(?:de\s+|para\s+|pra\s+)?{_DAY}$"),
    re.compile(rf"^(?:tenho|tem)\s+(?:algum\s+)?compromissos?\s+(?:para\s+|pra\s+)?{_DAY}$"),
]


def agenda_day(msg_norm: str) -> Optional[str]:
    """'hoje' | 'amanha' se a mensagem (ja sem acento/maiuscula) so pergunta pela agenda daquele dia; senao None."""
    for pat in _ASK:
        m = pat.match(msg_norm)
        if m:
            return m.group(1)
    return None


def day_bounds(day: str, now: datetime) -> tuple[datetime, datetime]:
    """(inicio, fim) do dia pedido, com o fuso de `now`. Hoje comeca agora (o que ja passou nao interessa)."""
    if day == "amanha":
        start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start = now
    return start, start.replace(hour=23, minute=59, second=59, microsecond=0)


def _hhmm(start: str) -> str:
    return start[11:16] if "T" in start and len(start) >= 16 else ""


def format_agenda(content: str, day: str) -> str:
    """Texto para a pessoa a partir do que a ferramenta de agenda devolveu (JSON). Nunca levanta erro."""
    label = "amanhã" if day == "amanha" else "hoje"
    try:
        events = json.loads(content)
    except (ValueError, TypeError):
        return "Não consegui ler a sua agenda agora. Tente de novo daqui a pouco."
    if not isinstance(events, list):
        return "Não consegui ler a sua agenda agora. Tente de novo daqui a pouco."
    if events and isinstance(events[0], dict) and "error" in events[0]:
        return "Não consegui ler a sua agenda agora. Em Conexões → Google, veja se o Google continua conectado."
    rows = []
    for e in events:
        if not isinstance(e, dict):
            continue
        title = " ".join(str(e.get("summary") or "Compromisso").split())[:100]
        when = _hhmm(str(e.get("start") or ""))
        rows.append(f"- {when + ' ' if when else 'Dia todo: '}{title}")
    if not rows:
        return f"Você não tem nenhum compromisso {label}. Dia livre!"
    plural = "compromissos" if len(rows) > 1 else "compromisso"
    return f"Para {label} você tem {len(rows)} {plural}:\n" + "\n".join(rows)
