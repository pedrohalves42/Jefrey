"""Lembretes: entende pedidos em portugues, guarda por usuario e entrega o que venceu.

O horario NAO depende do modelo de IA (modelos pequenos erram datas): um interpretador deterministico
le "amanha as 8h", "daqui a 20 minutos", "toda segunda as 9", "todo dia as 8 da manha" etc.
Entrega: o app consulta /reminders/due; um lembrete so sai da fila quando a tela confirma que mostrou
(ack), entao nada se perde se o app estava fechado na hora.
"""
from __future__ import annotations

import os
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Optional

WEEKDAYS = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6}
PT_WEEKDAYS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
PERIOD_HOUR = {"manha": 8, "tarde": 15, "noite": 20, "madrugada": 5}
DEFAULT_HOUR = 9  # "amanha" sem horario: 9h (a resposta diz o horario escolhido para o usuario corrigir)
MAX_TEXT = 300
MAX_PENDING = 200


def _norm(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def local_tz() -> tzinfo:
    name = os.getenv("JEFREY_TIMEZONE", "America/Sao_Paulo")
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        return datetime.now().astimezone().tzinfo or timezone.utc


# ---------------------------------------------------------------- interpretador de horario
@dataclass
class When:
    due: Optional[datetime]  # aware; None = nao deu para entender quando
    repeat: str = "none"  # none | daily | weekly
    assumed_time: bool = False  # True quando o horario foi assumido (9h)
    spans: tuple = ()  # trechos (inicio, fim) consumidos do texto normalizado


_NUMWORDS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "dez": 10, "quinze": 15,
             "vinte": 20, "trinta": 30}
_REL = re.compile(r"\b(?:daqui a|daqui|em)\s+(meia|\d+|" + "|".join(_NUMWORDS) + r")\s*(minutos?|min|horas?|h|dias?|semanas?)?\b")
_DAILY = re.compile(r"\b(?:todo dia|todos os dias|diariamente|todo santo dia)\b")
_WEEKLY = re.compile(r"\btoda?s?\s+(?:as\s+)?(segunda|terca|quarta|quinta|sexta|sabado|domingo)s?(?:-feira)?\b")
_WEEKDAY = re.compile(r"\b(?:na|no|em|para|pra|de)?\s*(segunda|terca|quarta|quinta|sexta|sabado|domingo)(?:-feira)?\b")
_DAY = re.compile(r"\b(depois de amanha|amanha|hoje)\b")
_PERIOD = re.compile(r"\b(?:de|da|pela|a)\s+(manha|tarde|noite|madrugada)\b")
_NOON = re.compile(r"\b(meio[- ]dia|meia[- ]noite)\b")
_TIME_AS = re.compile(r"\b(?:as|às)\s+(\d{1,2})(?:\s*(?:h|:|horas?)\s*(\d{2})?)?(?:\s*(?:min(?:utos?)?))?\b")
_TIME_H = re.compile(r"\b(\d{1,2})\s*h\s*(\d{2})?\b|\b(\d{1,2}):(\d{2})\b")


def parse_when(text: str, now: Optional[datetime] = None) -> When:
    """Le 'amanha as 8h', 'daqui a 20 minutos', 'toda sexta as 9', 'todo dia as 8 da manha'..."""
    tz = local_tz()
    now = (now or datetime.now(tz)).astimezone(tz)
    t = _norm(text or "")
    spans: list[tuple[int, int]] = []

    def take(m: "re.Match[str]") -> "re.Match[str]":
        spans.append((m.start(), m.end()))
        return m

    # ---- relativo: daqui a 20 minutos / em 2 horas / daqui a meia hora
    m = _REL.search(t)
    if m and (m.group(2) or m.group(1) == "meia"):
        take(m)
        n_raw, unit = m.group(1), (m.group(2) or "hora")
        n = 0.5 if n_raw == "meia" else float(_NUMWORDS.get(n_raw, n_raw if n_raw.isdigit() else 0))
        if n <= 0:
            return When(None, spans=tuple(spans))
        u = unit[0]
        delta = (timedelta(minutes=n) if unit.startswith("min") else
                 timedelta(hours=n) if u == "h" else timedelta(days=n) if u == "d" else timedelta(weeks=n))
        due = (now + delta).replace(second=0, microsecond=0)
        return When(due, spans=tuple(spans))

    repeat = "none"
    base_date = None  # date
    if (m := _DAILY.search(t)):
        take(m)
        repeat = "daily"
    elif (m := _WEEKLY.search(t)):
        take(m)
        repeat = "weekly"
        wd = WEEKDAYS[m.group(1)]
        base_date = now.date() + timedelta(days=(wd - now.weekday()) % 7)
    if base_date is None and repeat == "none":
        if (m := _DAY.search(t)):
            take(m)
            base_date = now.date() + timedelta(days={"hoje": 0, "amanha": 1, "depois de amanha": 2}[m.group(1)])
        elif (m := _WEEKDAY.search(t)):
            take(m)
            base_date = now.date() + timedelta(days=(WEEKDAYS[m.group(1)] - now.weekday()) % 7)

    # ---- horario
    hour = minute = None
    period = None
    if (m := _PERIOD.search(t)):
        take(m)
        period = m.group(1)
    if (m := _NOON.search(t)):
        take(m)
        hour, minute = (12, 0) if m.group(1).startswith("meio") else (0, 0)
    elif (m := _TIME_AS.search(t)):
        take(m)
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
    elif (m := _TIME_H.search(t)):
        take(m)
        hour = int(m.group(1) or m.group(3))
        minute = int(m.group(2) or m.group(4) or 0)
    if hour is not None:
        if period in ("tarde", "noite") and hour < 12:
            hour += 12
        if hour > 23 or minute > 59:
            return When(None, spans=tuple(spans))
    elif period:
        hour, minute = PERIOD_HOUR[period], 0

    assumed = False
    if hour is None:
        if base_date is None and repeat == "none":
            return When(None, spans=tuple(spans))  # nao entendi quando
        hour, minute, assumed = DEFAULT_HOUR, 0, True

    def at(d):
        return datetime(d.year, d.month, d.day, hour, minute, tzinfo=tz)

    if base_date is not None:
        due = at(base_date)
        if due <= now:  # hoje/dia da semana ja passou: proxima ocorrencia
            due = at(base_date + timedelta(days=7 if (repeat == "weekly" or _WEEKDAY.search(t)) else 1))
    else:  # so horario (ou todo dia as X): proxima vez que esse horario acontece
        due = at(now.date())
        if due <= now:
            due += timedelta(days=1)
    return When(due, repeat, assumed, tuple(spans))


# ---------------------------------------------------------------- pedido completo
_PREFIX = re.compile(
    r"^(?:por favor[, ]+|pode |poderia |voce pode |vc pode )*"
    r"(?:(?:me\s+)?(?:lembr[ae]r?|avis[ae]r?)(?:-me)?(?:\s+(?:de|que|para|pra))?|"
    r"(?:cri[ae]r?|faz(?:er)?|marc[ae]r?|adicion[ae]r?|coloc[ae]r?)\s+(?:um\s+)?lembrete(?:\s+(?:de|para|pra|que))?)\s+")
_TRAIL = re.compile(r"[\s,.;:!?-]+$")


@dataclass
class ReminderRequest:
    text: str
    when: When


def parse_request(message: str, now: Optional[datetime] = None) -> Optional[ReminderRequest]:
    """'me lembra de tomar o remedio amanha as 8h' -> texto 'tomar o remedio' + quando. None = nao e pedido de lembrete."""
    orig = (message or "").strip()
    n = _norm(orig)
    pm = _PREFIX.match(n)
    if not pm:
        return None
    same_len = len(orig) == len(n)
    rest_n, rest_o = n[pm.end():], (orig[pm.end():] if same_len else n[pm.end():])
    when = parse_when(rest_n, now)
    # remove do texto original os trechos de horario
    keep, last = [], 0
    for s, e in sorted(when.spans):
        keep.append(rest_o[last:s])
        last = e
    keep.append(rest_o[last:])
    text = " ".join("".join(keep).split())
    text = re.sub(r"^(?:de|que|para|pra)\s+", "", text, flags=re.I)
    text = re.sub(r"\s+(?:de|as|às|em|para|pra|no|na|a|e)$", "", _TRAIL.sub("", text), flags=re.I)
    text = _TRAIL.sub("", text).strip()
    if not text:
        return None
    return ReminderRequest(text[:MAX_TEXT], when)


def describe_due(due: datetime, now: Optional[datetime] = None) -> str:
    tz = local_tz()
    now = (now or datetime.now(tz)).astimezone(tz)
    d = due.astimezone(tz)
    delta_days = (d.date() - now.date()).days
    day = ("hoje" if delta_days == 0 else "amanhã" if delta_days == 1 else
           f"{PT_WEEKDAYS[d.weekday()]}, {d.day:02d}/{d.month:02d}" if delta_days < 7 else f"{d.day:02d}/{d.month:02d}/{d.year}")
    return f"{day} às {d:%H:%M}"


# ---------------------------------------------------------------- armazenamento
def _model():
    from sqlalchemy import Column, DateTime, String, Text
    from src.jefrey.core.db import Base

    existing = Base.metadata.tables.get("reminders")
    if existing is not None:
        return existing
    from sqlalchemy import Table
    return Table(
        "reminders", Base.metadata,
        Column("id", String(36), primary_key=True),
        Column("user_id", String(255), nullable=False, index=True),
        Column("text", Text, nullable=False),
        Column("due_at", DateTime, nullable=False, index=True),  # UTC sem fuso
        Column("repeat", String(10), nullable=False, default="none"),
        Column("status", String(10), nullable=False, default="pending"),  # pending | done | cancelled
        Column("created_at", DateTime, nullable=False),
    )


def _utc_naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _from_row(r) -> dict:
    due = r.due_at.replace(tzinfo=timezone.utc).astimezone(local_tz())
    return {"id": r.id, "text": r.text, "due_at": due.isoformat(), "due_label": describe_due(due),
            "repeat": r.repeat, "status": r.status}


class ReminderStore:
    """Tudo isolado por user_id: nunca le, apaga nem entrega lembrete de outro usuario."""

    def __init__(self):
        from src.jefrey.core.db import get_engine
        self.t = _model()
        self.engine = get_engine()
        self.t.create(self.engine, checkfirst=True)

    def add(self, user_id: str, text: str, due: datetime, repeat: str = "none") -> dict:
        from sqlalchemy import func, select
        if not user_id or user_id in ("system", "anonymous"):
            raise ValueError("usuario invalido")
        text = " ".join((text or "").split())[:MAX_TEXT]
        if not text:
            raise ValueError("lembrete vazio")
        if repeat not in ("none", "daily", "weekly"):
            raise ValueError("repeticao invalida")
        with self.engine.begin() as c:
            n = c.execute(select(func.count()).select_from(self.t).where(
                self.t.c.user_id == user_id, self.t.c.status == "pending")).scalar() or 0
            if n >= MAX_PENDING:
                raise ValueError(f"limite de {MAX_PENDING} lembretes pendentes")
            rid = str(uuid.uuid4())
            c.execute(self.t.insert().values(id=rid, user_id=user_id, text=text, due_at=_utc_naive(due),
                                             repeat=repeat, status="pending", created_at=_utc_naive(datetime.now(timezone.utc))))
            row = c.execute(self.t.select().where(self.t.c.id == rid)).one()
        return _from_row(row)

    def pending(self, user_id: str) -> list[dict]:
        with self.engine.connect() as c:
            rows = c.execute(self.t.select().where(self.t.c.user_id == user_id, self.t.c.status == "pending")
                             .order_by(self.t.c.due_at)).all()
        return [_from_row(r) for r in rows]

    def due(self, user_id: str, now: Optional[datetime] = None) -> list[dict]:
        cut = _utc_naive(now or datetime.now(timezone.utc))
        with self.engine.connect() as c:
            rows = c.execute(self.t.select().where(self.t.c.user_id == user_id, self.t.c.status == "pending",
                                                   self.t.c.due_at <= cut).order_by(self.t.c.due_at)).all()
        return [_from_row(r) for r in rows]

    def ack(self, user_id: str, rid: str, now: Optional[datetime] = None) -> bool:
        """A tela mostrou o lembrete: unico some; repetido vai para a proxima ocorrencia."""
        now_utc = _utc_naive(now or datetime.now(timezone.utc))
        with self.engine.begin() as c:
            row = c.execute(self.t.select().where(self.t.c.id == rid, self.t.c.user_id == user_id,
                                                  self.t.c.status == "pending")).first()
            if row is None:
                return False
            if row.repeat == "none":
                c.execute(self.t.update().where(self.t.c.id == rid).values(status="done"))
            else:
                step = timedelta(days=1 if row.repeat == "daily" else 7)
                nxt = row.due_at
                while nxt <= now_utc:
                    nxt += step
                c.execute(self.t.update().where(self.t.c.id == rid).values(due_at=nxt))
        return True

    def cancel(self, user_id: str, rid: str) -> bool:
        with self.engine.begin() as c:
            res = c.execute(self.t.update().where(self.t.c.id == rid, self.t.c.user_id == user_id,
                                                  self.t.c.status == "pending").values(status="cancelled"))
        return res.rowcount > 0
