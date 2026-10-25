"""WhatsApp guardado no banco (SQLAlchemy): conversas, rascunhos, aparelhos pareados. Regras em domain/whatsapp.py."""
from __future__ import annotations

import hashlib
import logging
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, func, select

from src.jefrey.domain.whatsapp import *  # noqa: F401,F403
from src.jefrey.domain.whatsapp import APPROVED_TTL_H, CHAT_LIMIT, DRAFT_TTL_H, HOUR_LIMIT, KEEP_DAYS, MAX_MSGS, MAX_REPLY, MAX_TEXT, MODES, PAIR_TTL_S, chat_key, has_secret  # noqa: F401

logger = logging.getLogger(__name__)

_pairing: dict[str, dict] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------- tabelas ----------------
def _tables():
    from sqlalchemy import Boolean, Column, DateTime, Integer, String, Table, Text

    from src.jefrey.core.db import Base

    md = Base.metadata
    dev = md.tables.get("wa_devices")
    if dev is None:
        dev = Table("wa_devices", md, Column("id", String(40), primary_key=True), Column("user_id", String(255), nullable=False, index=True),
                    Column("token_hash", String(64), nullable=False, index=True), Column("label", String(60), nullable=False),
                    Column("created_at", DateTime, nullable=False), Column("last_seen", DateTime, nullable=True))
    chats = md.tables.get("wa_chats")
    if chats is None:
        chats = Table("wa_chats", md, Column("id", String(40), primary_key=True), Column("user_id", String(255), nullable=False, index=True),
                      Column("ckey", String(100), nullable=False), Column("display", String(100), nullable=False),
                      Column("mode", String(10), nullable=False), Column("last_seen", DateTime, nullable=False))
    drafts = md.tables.get("wa_drafts")
    if drafts is None:
        drafts = Table("wa_drafts", md, Column("id", String(40), primary_key=True), Column("user_id", String(255), nullable=False, index=True),
                       Column("chat_id", String(40), nullable=False), Column("display", String(100), nullable=False),
                       Column("incoming", Text, nullable=False), Column("reply", Text, nullable=False), Column("why", String(200), nullable=False),
                       Column("status", String(12), nullable=False), Column("msg_ids", Text, nullable=False), Column("created_at", DateTime, nullable=False))
    prefs = md.tables.get("wa_prefs")
    if prefs is None:
        prefs = Table("wa_prefs", md, Column("user_id", String(255), primary_key=True), Column("paused", Boolean, nullable=False))
    seen = md.tables.get("wa_seen")
    if seen is None:
        seen = Table("wa_seen", md, Column("user_id", String(255), primary_key=True), Column("mid", String(120), primary_key=True),
                     Column("ts", DateTime, nullable=False))
    return dev, chats, drafts, prefs, seen


def _extra_tables():
    """Caixa de entrada (ultimo retrato da lista de conversas) e historico lido das conversas abertas."""
    from sqlalchemy import Boolean, Column, DateTime, Integer, String, Table, Text

    from src.jefrey.core.db import Base

    md = Base.metadata
    inbox = md.tables.get("wa_inbox")
    if inbox is None:
        inbox = Table("wa_inbox", md, Column("user_id", String(255), primary_key=True), Column("ckey", String(100), primary_key=True),
                      Column("display", String(100), nullable=False), Column("preview", String(200), nullable=False),
                      Column("unread", Integer, nullable=False), Column("ts", DateTime, nullable=False))
    msgs = md.tables.get("wa_msgs")
    if msgs is None:
        msgs = Table("wa_msgs", md, Column("user_id", String(255), primary_key=True), Column("ckey", String(100), primary_key=True),
                     Column("mid", String(120), primary_key=True), Column("text", Text, nullable=False),
                     Column("from_me", Boolean, nullable=False), Column("ts", DateTime, nullable=False))
    return inbox, msgs


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class WAStore:
    def __init__(self):
        from src.jefrey.core.db import get_engine

        self.dev, self.chats, self.drafts, self.prefs, self.seen = _tables()
        self.engine = get_engine()
        self.inbox, self.msgs = _extra_tables()
        for t in (self.dev, self.chats, self.drafts, self.prefs, self.seen, self.inbox, self.msgs):
            t.create(self.engine, checkfirst=True)

    # --- pareamento ---
    @staticmethod
    def begin_pairing(user_id: str, now: Optional[float] = None) -> dict:
        t = time.monotonic() if now is None else now
        for k in [k for k, v in _pairing.items() if v["exp"] < t]:
            _pairing.pop(k, None)
        for k in [k for k, v in _pairing.items() if v["user"] == user_id]:
            _pairing.pop(k, None)  # um codigo vivo por pessoa
        code = f"{secrets.randbelow(10**6):06d}"
        while code in _pairing:
            code = f"{secrets.randbelow(10**6):06d}"
        _pairing[code] = {"user": user_id, "exp": t + PAIR_TTL_S, "tries": 0}
        return {"code": code, "expires_in": PAIR_TTL_S}

    def complete_pairing(self, code: str, label: str, now: Optional[float] = None) -> Optional[str]:
        """Troca o codigo por um token de aparelho. O codigo vale uma vez; erros demais o invalidam."""
        t = time.monotonic() if now is None else now
        entry = _pairing.get((code or "").strip())
        if entry is None or entry["exp"] < t:
            return None
        _pairing.pop(code.strip(), None)
        token = secrets.token_urlsafe(32)
        with self.engine.begin() as c:
            c.execute(self.dev.insert().values(id=uuid.uuid4().hex, user_id=entry["user"], token_hash=_hash(token),
                                               label=" ".join((label or "Chrome").split())[:60], created_at=_now(), last_seen=None))
        return token

    def device_user(self, token: str) -> Optional[str]:
        if not token or len(token) > 200:
            return None
        with self.engine.begin() as c:
            row = c.execute(self.dev.select().where(self.dev.c.token_hash == _hash(token))).first()
            if row is None:
                return None
            c.execute(self.dev.update().where(self.dev.c.id == row.id).values(last_seen=_now()))
        return row.user_id

    def devices(self, user_id: str) -> list[dict]:
        with self.engine.connect() as c:
            rows = c.execute(self.dev.select().where(self.dev.c.user_id == user_id).order_by(self.dev.c.created_at)).fetchall()
        return [{"id": r.id, "label": r.label, "created_at": r.created_at.isoformat(), "last_seen": r.last_seen.isoformat() if r.last_seen else None} for r in rows]

    def seconds_since_seen(self, user_id: str) -> Optional[int]:
        """Ha quantos segundos a extensao falou com o Jefrey (None = nunca falou ou nao ha aparelho)."""
        seen = [d["last_seen"] for d in self.devices(user_id) if d["last_seen"]]
        if not seen:
            return None
        return max(0, int((_now() - datetime.fromisoformat(max(seen))).total_seconds()))

    def revoke_device(self, user_id: str, device_id: str) -> bool:
        with self.engine.begin() as c:
            return bool(c.execute(self.dev.delete().where((self.dev.c.id == device_id) & (self.dev.c.user_id == user_id))).rowcount)

    # --- pausa ---
    def paused(self, user_id: str) -> bool:
        with self.engine.connect() as c:
            r = c.execute(self.prefs.select().where(self.prefs.c.user_id == user_id)).first()
        return bool(r.paused) if r else False

    def set_paused(self, user_id: str, paused: bool) -> None:
        with self.engine.begin() as c:
            c.execute(self.prefs.delete().where(self.prefs.c.user_id == user_id))
            c.execute(self.prefs.insert().values(user_id=user_id, paused=bool(paused)))

    # --- conversas ---
    def touch_chat(self, user_id: str, display: str) -> dict:
        """Registra que a conversa existe. Nova conversa entra como 'pending' (nao e atendida ate a pessoa liberar)."""
        key, shown = chat_key(display), " ".join((display or "").split())[:100]
        if not key:
            raise ValueError("conversa sem nome")
        with self.engine.begin() as c:
            row = c.execute(self.chats.select().where((self.chats.c.user_id == user_id) & (self.chats.c.ckey == key))).first()
            if row is None:
                cid = uuid.uuid4().hex
                c.execute(self.chats.insert().values(id=cid, user_id=user_id, ckey=key, display=shown, mode="pending", last_seen=_now()))
                return {"id": cid, "display": shown, "mode": "pending"}
            c.execute(self.chats.update().where(self.chats.c.id == row.id).values(last_seen=_now()))
            return {"id": row.id, "display": row.display, "mode": row.mode}

    def list_chats(self, user_id: str) -> list[dict]:
        with self.engine.connect() as c:
            rows = c.execute(self.chats.select().where(self.chats.c.user_id == user_id).order_by(self.chats.c.last_seen.desc()).limit(200)).fetchall()
        return [{"id": r.id, "display": r.display, "mode": r.mode, "last_seen": r.last_seen.isoformat()} for r in rows]

    def set_mode(self, user_id: str, chat_id: str, mode: str) -> Optional[dict]:
        if mode not in MODES:
            raise ValueError("modo invalido")
        with self.engine.begin() as c:
            n = c.execute(self.chats.update().where((self.chats.c.id == chat_id) & (self.chats.c.user_id == user_id)).values(mode=mode)).rowcount
        return next((x for x in self.list_chats(user_id) if x["id"] == chat_id), None) if n else None

    def delete_chat(self, user_id: str, chat_id: str) -> bool:
        with self.engine.begin() as c:
            c.execute(self.drafts.delete().where((self.drafts.c.chat_id == chat_id) & (self.drafts.c.user_id == user_id)))
            return bool(c.execute(self.chats.delete().where((self.chats.c.id == chat_id) & (self.chats.c.user_id == user_id))).rowcount)

    # --- mensagens ja vistas / limites ---
    def is_new(self, user_id: str, mid: str) -> bool:
        mid = (mid or "")[:120]
        if not mid:
            return False
        with self.engine.begin() as c:
            if c.execute(self.seen.select().where((self.seen.c.user_id == user_id) & (self.seen.c.mid == mid))).first():
                return False
            c.execute(self.seen.insert().values(user_id=user_id, mid=mid, ts=_now()))
        return True

    def recent_drafts(self, user_id: str, chat_id: Optional[str], seconds: int) -> int:
        cut = _now() - timedelta(seconds=seconds)
        cond = and_(self.drafts.c.user_id == user_id, self.drafts.c.created_at >= cut)
        if chat_id:
            cond = and_(cond, self.drafts.c.chat_id == chat_id)
        with self.engine.connect() as c:
            return c.execute(select(func.count()).select_from(self.drafts).where(cond)).scalar() or 0

    # --- rascunhos ---
    def add_draft(self, user_id: str, chat: dict, incoming: str, reply: str, why: str, status: str, msg_ids: list[str]) -> dict:
        did = uuid.uuid4().hex
        with self.engine.begin() as c:
            c.execute(self.drafts.insert().values(id=did, user_id=user_id, chat_id=chat["id"], display=chat["display"], incoming=incoming[:4000],
                                                  reply=reply[:MAX_REPLY], why=why[:200], status=status, msg_ids=",".join(msg_ids)[:1000], created_at=_now()))
        return self.get_draft(user_id, did)  # type: ignore[return-value]

    @staticmethod
    def _draft(r) -> dict:
        return {"id": r.id, "chat": r.display, "incoming": r.incoming, "reply": r.reply, "why": r.why, "status": r.status, "created_at": r.created_at.isoformat()}

    def get_draft(self, user_id: str, did: str) -> Optional[dict]:
        with self.engine.connect() as c:
            r = c.execute(self.drafts.select().where((self.drafts.c.id == did) & (self.drafts.c.user_id == user_id))).first()
        return self._draft(r) if r else None

    def list_drafts(self, user_id: str, status: Optional[str] = None, limit: int = 50) -> list[dict]:
        q = self.drafts.select().where(self.drafts.c.user_id == user_id)
        if status:
            q = q.where(self.drafts.c.status == status)
        with self.engine.connect() as c:
            rows = c.execute(q.order_by(self.drafts.c.created_at.desc()).limit(limit)).fetchall()
        return [self._draft(r) for r in rows]

    def decide(self, user_id: str, did: str, decision: str, text: Optional[str] = None) -> Optional[dict]:
        """A pessoa aprova (opcionalmente editando) ou recusa. So rascunhos 'pending' mudam."""
        if decision not in ("approve", "reject"):
            raise ValueError("decisao invalida")
        vals: dict[str, Any] = {"status": "approved" if decision == "approve" else "rejected"}
        if decision == "approve":
            current = self.get_draft(user_id, did)
            clean = " ".join((text if text is not None else (current or {}).get("reply", "")).split())[:MAX_REPLY]
            if current is not None and (not clean or has_secret(clean)):
                raise ValueError("Esse texto não pode ser enviado (vazio ou com dado sensível).")
            vals["reply"] = clean
        with self.engine.begin() as c:
            n = c.execute(self.drafts.update().where((self.drafts.c.id == did) & (self.drafts.c.user_id == user_id) & (self.drafts.c.status == "pending")).values(**vals)).rowcount
        return self.get_draft(user_id, did) if n else None

    def outbox(self, user_id: str) -> list[dict]:
        """Rascunhos aprovados (pela pessoa ou automaticamente) esperando a extensao enviar. Expira os pendentes antigos."""
        cut = _now() - timedelta(hours=DRAFT_TTL_H)
        with self.engine.begin() as c:
            c.execute(self.drafts.update().where((self.drafts.c.user_id == user_id) & (self.drafts.c.status == "pending") & (self.drafts.c.created_at < cut)).values(status="expired"))
            old = _now() - timedelta(hours=APPROVED_TTL_H)
            c.execute(self.drafts.update().where((self.drafts.c.user_id == user_id) & (self.drafts.c.status == "approved") & (self.drafts.c.created_at < old)).values(status="expired"))
            rows = c.execute(self.drafts.select().where((self.drafts.c.user_id == user_id) & (self.drafts.c.status == "approved")).order_by(self.drafts.c.created_at).limit(5)).fetchall()
        return [{"id": r.id, "chat": r.display, "text": r.reply} for r in rows]

    def queue_message(self, user_id: str, chat_id: str, text: str) -> dict:
        """Mensagem escrita (ou revisada) pela PESSOA: vai direto para a fila da extensao. Nunca com dado sensivel."""
        chat = next((c for c in self.list_chats(user_id) if c["id"] == chat_id), None)
        if chat is None:
            raise LookupError("conversa nao encontrada")
        clean = " ".join((text or "").split())[:MAX_REPLY]
        if not clean or has_secret(clean):
            raise ValueError("Esse texto não pode ser enviado (vazio ou com dado sensível).")
        return self.add_draft(user_id, chat, "", clean, "escrita por você", "approved", [])

    def mark_sent(self, user_id: str, did: str, ok: bool) -> bool:
        with self.engine.begin() as c:
            return bool(c.execute(self.drafts.update().where((self.drafts.c.id == did) & (self.drafts.c.user_id == user_id) & (self.drafts.c.status == "approved"))
                                  .values(status="sent" if ok else "failed")).rowcount)

    # --- caixa de entrada e historico ---
    def save_inbox(self, user_id: str, items: list[dict]) -> list[dict]:
        """Guarda o retrato da lista de conversas. Devolve as que ganharam mensagens nao lidas desde o retrato anterior."""
        grew: list[dict] = []
        with self.engine.begin() as c:
            old = {r.ckey: r.unread for r in c.execute(self.inbox.select().where(self.inbox.c.user_id == user_id)).fetchall()}
            c.execute(self.inbox.delete().where(self.inbox.c.user_id == user_id))
            seen_keys: set[str] = set()
            for it in items:
                key = chat_key(it["title"])
                if not key or key in seen_keys:
                    continue
                seen_keys.add(key)
                c.execute(self.inbox.insert().values(user_id=user_id, ckey=key, display=it["title"], preview=it["preview"][:200], unread=it["unread"], ts=_now()))
                if it["unread"] > old.get(key, 0):
                    grew.append(it)
        return grew

    def inbox_items(self, user_id: str) -> list[dict]:
        with self.engine.connect() as c:
            rows = c.execute(self.inbox.select().where(self.inbox.c.user_id == user_id).order_by(self.inbox.c.unread.desc(), self.inbox.c.ts.desc())).fetchall()
        return [{"title": r.display, "preview": r.preview, "unread": r.unread, "ts": r.ts.isoformat()} for r in rows]

    def inbox_age_s(self, user_id: str) -> Optional[int]:
        with self.engine.connect() as c:
            ts = c.execute(select(func.max(self.inbox.c.ts)).where(self.inbox.c.user_id == user_id)).scalar()
        return max(0, int((_now() - ts).total_seconds())) if ts else None

    def save_history(self, user_id: str, chat: str, msgs: list[dict]) -> int:
        key, n = chat_key(chat), 0
        if not key:
            return 0
        with self.engine.begin() as c:
            for m in msgs:
                mid = m["id"][:120]
                if c.execute(self.msgs.select().where((self.msgs.c.user_id == user_id) & (self.msgs.c.ckey == key) & (self.msgs.c.mid == mid))).first():
                    continue
                c.execute(self.msgs.insert().values(user_id=user_id, ckey=key, mid=mid, text=m["text"], from_me=bool(m["from_me"]), ts=_now()))
                n += 1
        return n

    def history(self, user_id: str, chat: str, limit: int = 10) -> list[dict]:
        key = chat_key(chat)
        with self.engine.connect() as c:
            rows = c.execute(self.msgs.select().where((self.msgs.c.user_id == user_id) & (self.msgs.c.ckey == key)).order_by(self.msgs.c.ts.desc()).limit(limit)).fetchall()
        return [{"id": r.mid, "text": r.text, "from_me": bool(r.from_me)} for r in reversed(rows)]

    def purge(self, days: int = KEEP_DAYS) -> int:
        cut = _now() - timedelta(days=days)
        with self.engine.begin() as c:
            c.execute(self.msgs.delete().where(self.msgs.c.ts < cut))
            c.execute(self.seen.delete().where(self.seen.c.ts < cut))
            return c.execute(self.drafts.delete().where(self.drafts.c.created_at < cut)).rowcount or 0

    def forget_all(self, user_id: str) -> int:
        with self.engine.begin() as c:
            n = c.execute(self.drafts.delete().where(self.drafts.c.user_id == user_id)).rowcount or 0
            c.execute(self.chats.delete().where(self.chats.c.user_id == user_id))
            c.execute(self.seen.delete().where(self.seen.c.user_id == user_id))
            c.execute(self.dev.delete().where(self.dev.c.user_id == user_id))
            c.execute(self.inbox.delete().where(self.inbox.c.user_id == user_id))
            c.execute(self.msgs.delete().where(self.msgs.c.user_id == user_id))
            c.execute(self.prefs.delete().where(self.prefs.c.user_id == user_id))
        return n
