"""Casos de uso da proatividade: resumo do dia (de manha) e avisos de lembretes, sem incomodar.

O resumo e montado por regras (sem IA): agenda do dia dos lembretes, o que ficou atrasado, o que o Jefrey estudou
enquanto a pessoa estava fora e, se for o dia, o aniversario. Poucos avisos, nunca de madrugada; lembretes sempre chegam.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from src.jefrey.application import notify
from src.jefrey.domain.briefing import NUDGE_AFTER, birthday_today, build_text
from src.jefrey.domain.reminders import local_tz
from src.jefrey.ports.registry import use

logger = logging.getLogger(__name__)


def generate(user_id: str, now: datetime, store: Any = None) -> str:
    """Monta e guarda o resumo de hoje para a pessoa."""
    env = use("briefing_env")
    store = store or env.store()
    tz = now.tzinfo
    pending = env.pending_reminders(user_id)
    today_r, overdue = [], []
    for r in pending:
        due = datetime.fromisoformat(r["due_at"]).astimezone(tz)
        if due.date() == now.date() and due >= now:
            today_r.append(r)
        elif due < now:
            overdue.append(r)
    since = (now - timedelta(hours=24)).astimezone(timezone.utc).replace(tzinfo=None).isoformat()
    studied = [g for g in env.guides(user_id) if g["created_at"] >= since]
    facts = env.fact_texts(user_id)
    yday = env.diary_day(user_id, (now.date() - timedelta(days=1)).isoformat())
    text = build_text(name=env.person_name(user_id), now=now, today_reminders=today_r, overdue=overdue, studied=studied,
                      birthday=birthday_today(facts, now.date()), yesterday=yday)
    store.put(user_id, now.date().isoformat(), text)
    return text


async def briefing_tick(now: Optional[datetime] = None, store: Any = None) -> list[str]:
    """Gera o resumo de quem ja passou da hora escolhida e ainda nao tem o de hoje. Devolve os usuarios atendidos."""
    env = use("briefing_env")
    now = now or datetime.now(local_tz())
    store = store or env.store()
    done: list[str] = []
    for uid in env.known_users():
        try:
            prefs = store.get_prefs(uid)
            if not prefs["enabled"] or now.hour < prefs["hour"] or store.get(uid, now.date().isoformat()) is not None:
                continue
            text = generate(uid, now, store)
            done.append(uid)
            if prefs["notify"]:
                notify.notify(uid, "Resumo do dia", text.splitlines()[0] + " Toque para ver o resumo.", now=now)
        except Exception as e:
            logger.warning("resumo do dia falhou: %s", type(e).__name__)
    return done


_notified: set[str] = set()


_nudged: set[str] = set()


def _nudge_overdue(uid: str, r: dict, now: Optional[datetime]) -> None:
    """Uma hora depois, se a pessoa nao deu ciente, um toque gentil (uma vez so; respeita o silencio da noite e o limite do dia)."""
    if r["id"] in _nudged:
        return
    try:
        due = datetime.fromisoformat(r["due_at"])
        ref = now or datetime.now(due.tzinfo or timezone.utc)
        if ref - due < NUDGE_AFTER:
            return
    except (KeyError, ValueError, TypeError):
        return
    if notify.notify(uid, "Passou do horário", f"{r['text']} ficou em aberto. Quer que eu remarque?", now=now):
        _nudged.add(r["id"])


async def reminder_tick(now: Optional[datetime] = None) -> list[str]:
    """Avisa (balao do Windows) os lembretes que venceram, uma vez cada. A tela continua mostrando ate a pessoa dar ciente."""
    env = use("briefing_env")
    sent: list[str] = []
    for uid in env.known_users():
        try:
            for r in env.due_reminders(uid, now.astimezone(timezone.utc) if now else None):
                if r["id"] in _notified:
                    _nudge_overdue(uid, r, now)
                    continue
                _notified.add(r["id"])
                if notify.notify(uid, "Lembrete", r["text"], urgent=True, now=now):
                    sent.append(r["id"])
        except Exception as e:
            logger.warning("aviso de lembrete falhou: %s", type(e).__name__)
    if len(_notified) > 5000:
        _notified.clear()
    return sent
