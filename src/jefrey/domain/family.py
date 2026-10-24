"""Modo familia (REGRAS PURAS): resumo semanal para um cuidador, so com o consentimento da pessoa.

O resumo leva SO contagens (nunca o texto das conversas, lembretes ou mensagens). O Jefrey nunca envia sozinho:
oferece a mensagem e o envio passa pela aprovacao de sempre (enviar mensagem e acao de risco).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

OFFER_WEEKDAY = 6  # domingo
OFFER_FROM_HOUR = 18


def compose(name: str, caregiver: str, pending_reminders: int) -> str:
    who = (name or "").strip() or "A pessoa"
    greet = f"Oi, {caregiver.strip()}!" if caregiver.strip() else "Oi!"
    if pending_reminders > 0:
        tail = f" Ainda tem {pending_reminders} {'lembrete' if pending_reminders == 1 else 'lembretes'} para fazer."
    else:
        tail = " Está com os lembretes em dia."
    return f"{greet} Resumo da semana de {who}: o Jefrey está funcionando e {who} segue usando.{tail}"


def offer_due(now: datetime, last_offer_iso: Optional[str], enabled: bool, contact: str) -> bool:
    """So oferece com consentimento e contato, no domingo a noite, uma vez por semana."""
    if not enabled or not (contact or "").strip():
        return False
    if now.weekday() != OFFER_WEEKDAY or now.hour < OFFER_FROM_HOUR:
        return False
    return last_offer_iso != now.date().isoformat()
