"""Resumo do dia (REGRAS PURAS): reconhece o pedido e monta a frase falada com agenda, lembretes e clima.

Sem modelo de IA: e rapido, nao inventa nada e nunca mostra texto interno (blocos entre colchetes).
Fonte que nao respondeu (None) e dita com clareza; as outras continuam aparecendo.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Optional

_GREETING = re.compile(r"^(?:oi|ola|e ai|ei|hey|jefrey|bom dia|boa tarde|boa noite)(?:\s+|$)")
_DAY_GREETING = re.compile(r"^(?:bom dia|boa tarde|boa noite)$")
_ASK = [
    re.compile(r"^o que (?:eu )?tenho (?:pra|para|de) hoje$"),
    re.compile(r"^o que (?:eu )?tenho hoje$"),
    re.compile(r"^o que tem (?:pra|para) hoje$"),
    re.compile(r"^o que (?:ta|esta) rolando hoje$"),
    re.compile(r"^como (?:esta|vai|e) (?:o )?meu dia(?: hoje)?$"),
    re.compile(r"^(?:me )?(?:da|passa|faz|mostra|conta) (?:o )?resumo(?: do dia| de hoje)?$"),
    re.compile(r"^resumo(?: do dia| de hoje)$"),
    re.compile(r"^meu dia(?: hoje)?$"),
    re.compile(r"^me atualiza(?: do dia)?$"),
]
MAX_ITEMS = 4


def _plain(text: str) -> str:
    s = unicodedata.normalize("NFD", text or "").encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s)).strip()


def asks_daily_summary(message: str) -> bool:
    """True para 'bom dia', 'o que eu tenho pra hoje', 'como esta o meu dia', 'resumo do dia'. Nao pega pedidos com outro objetivo."""
    msg = _plain(message)
    if not msg:
        return False
    if _DAY_GREETING.match(msg):
        return True
    rest, seen_day_greeting = msg, False
    while True:
        m = _GREETING.match(rest)
        if not m:
            break
        seen_day_greeting = seen_day_greeting or bool(re.match(r"(?:bom dia|boa tarde|boa noite)", m.group(0)))
        rest = rest[m.end():].strip()
    if not rest:
        return seen_day_greeting
    return any(p.match(rest) for p in _ASK)


def greeting_for(now: datetime) -> str:
    return "Bom dia" if 5 <= now.hour < 12 else "Boa tarde" if 12 <= now.hour < 18 else "Boa noite"


def _agenda_line(agenda: list[dict]) -> str:
    itens = []
    for e in agenda[:MAX_ITEMS]:
        quando = f"{e['time']} " if e.get("time") else "dia todo: "
        itens.append(f"{quando}{e.get('title') or 'Compromisso'}")
    resto = len(agenda) - MAX_ITEMS
    extra = f" e mais {resto}" if resto > 0 else ""
    plural = "compromissos" if len(agenda) > 1 else "compromisso"
    return f"Na agenda você tem {len(agenda)} {plural}: " + "; ".join(itens) + extra + "."


def compose(*, name: Optional[str], now: datetime, agenda: Optional[list[dict]], reminders: Optional[list[dict]], weather: Optional[dict]) -> str:
    """Frase falada do dia. `None` numa fonte = nao consegui ver; lista vazia = nao ha nada."""
    saud = greeting_for(now)
    partes = [f"{saud}, {name}." if name else f"{saud}."]
    if agenda is None:
        partes.append("Não consegui ver a sua agenda agora.")
    elif agenda:
        partes.append(_agenda_line(agenda))
    if reminders:
        itens = [f"{r['text']} ({r['due_label']})" if r.get("due_label") else str(r["text"]) for r in reminders[:MAX_ITEMS]]
        partes.append("Lembretes: " + "; ".join(itens) + ".")
    elif reminders is None:
        partes.append("Não consegui ver os seus lembretes agora.")
    if weather and weather.get("summary"):
        partes.append(str(weather["summary"]))
    if agenda == [] and not reminders:
        partes.append("Você não tem compromissos nem lembretes para hoje: dia livre!")
    return " ".join(partes)
