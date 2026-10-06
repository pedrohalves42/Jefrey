"""Proatividade: resumo do dia (de manha) e avisos de lembretes, sem incomodar.

O resumo e montado por regras (sem IA): agenda do dia dos lembretes, o que ficou atrasado, o que o Jefrey estudou
enquanto a pessoa estava fora e, se for o dia, o aniversario. Poucos avisos, nunca de madrugada; lembretes sempre chegam.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import inspect, select

logger = logging.getLogger(__name__)

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


def _tables():
    from sqlalchemy import Boolean, Column, DateTime, Integer, String, Table, Text

    from src.jefrey.core.db import Base

    md = Base.metadata
    br = md.tables.get("briefings")
    if br is None:
        br = Table("briefings", md, Column("user_id", String(255), primary_key=True), Column("day", String(10), primary_key=True),
                   Column("text", Text, nullable=False), Column("seen", Boolean, nullable=False), Column("created_at", DateTime, nullable=False))
    pr = md.tables.get("proactive_prefs")
    if pr is None:
        pr = Table("proactive_prefs", md, Column("user_id", String(255), primary_key=True), Column("enabled", Boolean, nullable=False),
                   Column("hour", Integer, nullable=False), Column("notify", Boolean, nullable=False))
    return br, pr


class BriefingStore:
    def __init__(self):
        from src.jefrey.core.db import get_engine

        self.t, self.prefs = _tables()
        self.engine = get_engine()
        self.t.create(self.engine, checkfirst=True)
        self.prefs.create(self.engine, checkfirst=True)

    def get_prefs(self, user_id: str) -> dict:
        with self.engine.connect() as c:
            r = c.execute(self.prefs.select().where(self.prefs.c.user_id == user_id)).first()
        return {"enabled": True, "hour": DEFAULT_HOUR, "notify": True} if r is None else {"enabled": bool(r.enabled), "hour": int(r.hour), "notify": bool(r.notify)}

    def set_prefs(self, user_id: str, *, enabled: Optional[bool] = None, hour: Optional[int] = None, notify: Optional[bool] = None) -> dict:
        if not user_id or user_id in ("system", "anonymous"):
            raise ValueError("usuario invalido")
        cur = self.get_prefs(user_id)
        if enabled is not None:
            cur["enabled"] = bool(enabled)
        if notify is not None:
            cur["notify"] = bool(notify)
        if hour is not None:
            if not 5 <= hour <= 12:
                raise ValueError("O resumo da manhã pode ser entre 5h e 12h.")
            cur["hour"] = int(hour)
        with self.engine.begin() as c:
            c.execute(self.prefs.delete().where(self.prefs.c.user_id == user_id))
            c.execute(self.prefs.insert().values(user_id=user_id, **cur))
        return cur

    def get(self, user_id: str, day: str) -> Optional[dict]:
        with self.engine.connect() as c:
            r = c.execute(self.t.select().where((self.t.c.user_id == user_id) & (self.t.c.day == day))).first()
        return {"day": r.day, "text": r.text, "seen": bool(r.seen)} if r else None

    def all(self, user_id: str, limit: int = 400) -> list[dict]:
        with self.engine.connect() as c:
            rows = c.execute(self.t.select().where(self.t.c.user_id == user_id).order_by(self.t.c.day.desc()).limit(limit)).fetchall()
        return [{"day": r.day, "text": r.text} for r in rows]

    def put(self, user_id: str, day: str, text: str) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self.engine.begin() as c:
            c.execute(self.t.delete().where((self.t.c.user_id == user_id) & (self.t.c.day == day)))
            c.execute(self.t.insert().values(user_id=user_id, day=day, text=text[:1500], seen=False, created_at=now))

    def mark_seen(self, user_id: str, day: str) -> bool:
        with self.engine.begin() as c:
            return bool(c.execute(self.t.update().where((self.t.c.user_id == user_id) & (self.t.c.day == day)).values(seen=True)).rowcount)

    def forget_all(self, user_id: str) -> int:
        with self.engine.begin() as c:
            c.execute(self.prefs.delete().where(self.prefs.c.user_id == user_id))
            return c.execute(self.t.delete().where(self.t.c.user_id == user_id)).rowcount or 0


def known_users() -> list[str]:
    """Pessoas conhecidas (com nome, fatos, assuntos ou lembretes)."""
    from src.jefrey.core.db import Base, get_engine

    eng = get_engine()
    insp = inspect(eng)
    ids: set[str] = set()
    with eng.connect() as c:
        for name in ("user_profile", "learned_facts", "study_topics", "reminders"):
            t = Base.metadata.tables.get(name)
            if t is not None and insp.has_table(name):
                ids |= {r[0] for r in c.execute(select(t.c.user_id).distinct())}
    return sorted(u for u in ids if u and u not in ("system", "anonymous"))


def generate(user_id: str, now: datetime, store: Optional[BriefingStore] = None) -> str:
    """Monta e guarda o resumo de hoje para a pessoa."""
    from src.jefrey.core.diary import DiaryStore
    from src.jefrey.core.learning import FactStore
    from src.jefrey.core.profile import ProfileStore
    from src.jefrey.core.reminders import ReminderStore
    from src.jefrey.core.studies import StudyStore

    store = store or BriefingStore()
    tz = now.tzinfo
    pending = ReminderStore().pending(user_id)
    today_r, overdue = [], []
    for r in pending:
        due = datetime.fromisoformat(r["due_at"]).astimezone(tz)
        if due.date() == now.date() and due >= now:
            today_r.append(r)
        elif due < now:
            overdue.append(r)
    since = (now - timedelta(hours=24)).astimezone(timezone.utc).replace(tzinfo=None).isoformat()
    studied = [g for g in StudyStore().all_guides(user_id) if g["created_at"] >= since]
    facts = [f["text"] for f in FactStore().active(user_id, 200)]
    yday = DiaryStore().get(user_id, (now.date() - timedelta(days=1)).isoformat())
    text = build_text(name=ProfileStore().get_name(user_id), now=now, today_reminders=today_r, overdue=overdue, studied=studied,
                      birthday=birthday_today(facts, now.date()), yesterday=yday)
    store.put(user_id, now.date().isoformat(), text)
    return text


async def briefing_tick(now: Optional[datetime] = None, store: Optional[BriefingStore] = None) -> list[str]:
    """Gera o resumo de quem ja passou da hora escolhida e ainda nao tem o de hoje. Devolve os usuarios atendidos."""
    from src.jefrey.core import notify
    from src.jefrey.core.reminders import local_tz

    now = now or datetime.now(local_tz())
    store = store or BriefingStore()
    done: list[str] = []
    for uid in known_users():
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
NUDGE_AFTER = timedelta(hours=1)


def _nudge_overdue(uid: str, r: dict, now: Optional[datetime]) -> None:
    """Uma hora depois, se a pessoa nao deu ciente, um toque gentil (uma vez so; respeita o silencio da noite e o limite do dia)."""
    from src.jefrey.core import notify

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
    from src.jefrey.core import notify
    from src.jefrey.core.reminders import ReminderStore

    sent: list[str] = []
    store = ReminderStore()
    for uid in known_users():
        try:
            for r in store.due(uid, now.astimezone(timezone.utc) if now else None):
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
