"""Proatividade: resumo do dia (de manha) e avisos de lembretes, sem incomodar.

O resumo e montado por regras (sem IA): agenda do dia dos lembretes, o que ficou atrasado, o que o Jefrey estudou
enquanto a pessoa estava fora e, se for o dia, o aniversario. Poucos avisos, nunca de madrugada; lembretes sempre chegam.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional

DEFAULT_HOUR = 8
MAX_ITEMS = 5
_MONTHS = {"janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
           "outubro": 10, "novembro": 11, "dezembro": 12, "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8,
           "set": 9, "out": 10, "nov": 11, "dez": 12}


def greeting_for(hour: int) -> str:
    return "Bom dia" if hour < 12 else "Boa tarde" if hour < 18 else "Boa noite"


def birthday_today(fact_texts: list[str], today: date) -> bool:
    for t in fact_texts:
        m = re.search(r"[Aa]niversário: dia (\d{1,2}) de ([a-zç0-9]+)", t)
        if not m:
            continue
        month = _MONTHS.get(m.group(2).lower()) or (int(m.group(2)) if m.group(2).isdigit() else 0)
        if int(m.group(1)) == today.day and month == today.month:
            return True
    return False


def build_text(*, name: Optional[str], now: datetime, today_reminders: list[dict], overdue: list[dict], studied: list[dict],
               birthday: bool = False, yesterday: Optional[str] = None) -> str:
    who = f", {name}" if name else ""
    lines = [f"{greeting_for(now.hour)}{who}!"]
    if birthday:
        lines.append("Hoje é o seu aniversário. Parabéns! 🎉")
    if overdue:
        lines.append("Ficou pendente: " + "; ".join(r["text"] for r in overdue[:MAX_ITEMS]) + ".")
    if today_reminders:
        lines.append("Hoje você tem: " + "; ".join(f"{r['text']} ({r['due_label'].split(' às ')[-1]})" for r in today_reminders[:MAX_ITEMS]) + ".")
    for g in studied[:2]:
        lines.append(f"Enquanto você estava fora, estudei sobre {g['title']}. Quer ver o guia? Está em Estudos.")
    if yesterday:
        lines.append("Ontem: " + yesterday)
    if len(lines) == 1:
        lines.append("Dia tranquilo por aqui. Se quiser, me conta o que você vai fazer hoje.")
    return "\n".join(lines)


NUDGE_AFTER = timedelta(hours=1)
