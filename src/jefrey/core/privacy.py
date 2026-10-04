"""Seus dados (LGPD): ver o que o Jefrey guarda, baixar uma copia e apagar tudo.

"Apagar tudo" remove os dados PESSOAIS da pessoa (nome, conversas, fatos, diario, estudos, resumos, lembretes, notas e memorias,
WhatsApp e conexoes com o Google). Nao remove a escolha da inteligencia (modelo/chave), que e do programa e nao da pessoa.
Registros de seguranca (auditoria de aprovacoes) ficam: nao tem o texto das conversas.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)

TERMS_VERSION = "2026-10-04"


class ConsentStore:
    """Aceite dos termos e da politica de privacidade (por pessoa e por versao). Fica mesmo apos "apagar tudo"."""

    def __init__(self):
        from sqlalchemy import Column, DateTime, String, Table

        from src.jefrey.core.db import Base, get_engine

        t = Base.metadata.tables.get("consents")
        if t is None:
            t = Table("consents", Base.metadata, Column("user_id", String(255), primary_key=True), Column("version", String(20), primary_key=True),
                      Column("accepted_at", DateTime, nullable=False))
        self.t, self.engine = t, get_engine()
        self.t.create(self.engine, checkfirst=True)

    def accepted(self, user_id: str, version: str = TERMS_VERSION) -> bool:
        with self.engine.connect() as c:
            return c.execute(self.t.select().where((self.t.c.user_id == user_id) & (self.t.c.version == version))).first() is not None

    def accept(self, user_id: str, version: str = TERMS_VERSION) -> None:
        if not user_id or user_id in ("system", "anonymous"):
            raise ValueError("usuario invalido")
        if self.accepted(user_id, version):
            return
        with self.engine.begin() as c:
            c.execute(self.t.insert().values(user_id=user_id, version=version, accepted_at=datetime.now(timezone.utc).replace(tzinfo=None)))


def documents() -> dict:
    """Textos legais empacotados com o programa (sem os comentarios internos de revisao)."""
    import re
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "legal"
    out = {"version": TERMS_VERSION}
    for key, name in (("termos", "termos.md"), ("privacidade", "privacidade.md")):
        text = (base / name).read_text(encoding="utf-8")
        out[key] = re.sub(r"<!--.*?-->\s*", "", text, flags=re.S).strip()
    return out


def _safe(fn: Callable[[], Any], default: Any = None) -> Any:
    try:
        return fn()
    except Exception as e:  # uma parte quebrada nao pode impedir a pessoa de ver/apagar o resto
        logger.warning("privacidade: parte indisponivel (%s)", type(e).__name__)
        return default


def _memories(user_id: str) -> list[dict]:
    from src.jefrey.core.memory import get_memory_manager

    lt = get_memory_manager().long_term
    return lt.list_recent(limit=100000, user_id=user_id)


def export_all(user_id: str) -> dict:
    """Tudo que o Jefrey guarda sobre a pessoa, em um dicionario legivel (vira JSON)."""
    from src.jefrey.core.briefing import BriefingStore
    from src.jefrey.core.diary import DiaryStore
    from src.jefrey.core.google_oauth import status as google_status
    from src.jefrey.core.history import HistoryStore
    from src.jefrey.core.learning import FactStore
    from src.jefrey.core.profile import ProfileStore
    from src.jefrey.core.reminders import ReminderStore
    from src.jefrey.core.studies import StudyStore
    from src.jefrey.core.wa_web import WAStore

    out: dict[str, Any] = {"gerado_em": datetime.now(timezone.utc).isoformat(), "pessoa": user_id}
    out["nome"] = _safe(lambda: ProfileStore().get_name(user_id))
    out["o_que_aprendi"] = _safe(lambda: [{"tipo": f["kind"], "texto": f["text"], "delicado": f["sensitive"], "desde": f["created_at"]}
                                          for f in FactStore().active(user_id, 1000)], [])
    out["diario"] = _safe(lambda: DiaryStore().recent(user_id, 400), [])
    st = StudyStore()
    out["estudos"] = _safe(lambda: [{"assunto": t["title"], "nivel": t["level_label"], "guia": (st.latest_guide(user_id, t["id"]) or {}).get("body"),
                                     "fontes": (st.latest_guide(user_id, t["id"]) or {}).get("sources", [])} for t in st.list_topics(user_id)], [])
    out["resumos_da_manha"] = _safe(lambda: [{"dia": b["day"], "texto": b["text"]} for b in BriefingStore().all(user_id)], [])
    out["lembretes_pendentes"] = _safe(lambda: [{"texto": r["text"], "quando": r["due_label"]} for r in ReminderStore().pending(user_id)], [])
    out["memorias_e_notas"] = _safe(lambda: [{"texto": m["content"], "quando": m["metadata"].get("timestamp")} for m in _memories(user_id)], [])
    out["conversas"] = _safe(lambda: _history_dump(HistoryStore(), user_id), [])
    wa = WAStore()
    out["whatsapp"] = _safe(lambda: {"conversas_liberadas": [{"nome": c["display"], "modo": c["mode"]} for c in wa.list_chats(user_id)],
                                     "respostas": [{"conversa": d["chat"], "mensagem_recebida": d["incoming"], "resposta": d["reply"], "situacao": d["status"]}
                                                   for d in wa.list_drafts(user_id, None, 500)]}, {})
    g = _safe(lambda: google_status(user_id), {})
    out["google"] = {"conectado": bool(g.get("connected")), "email": g.get("email"), "servicos": g.get("services", [])}
    return out


def _history_dump(h, user_id: str) -> list[dict]:
    with h.engine.connect() as c:
        rows = c.execute(h.t.select().where(h.t.c.user_id == user_id).order_by(h.t.c.id)).fetchall()
    return [{"quando": r.ts.isoformat(), "quem": "voce" if r.role == "user" else "jefrey", "texto": r.content} for r in rows]


def summary(user_id: str) -> dict:
    """Contagens simples para a tela (sem o conteudo)."""
    d = export_all(user_id)
    return {"nome": bool(d["nome"]), "fatos": len(d["o_que_aprendi"]), "diario": len(d["diario"]), "assuntos": len(d["estudos"]),
            "lembretes": len(d["lembretes_pendentes"]), "memorias": len(d["memorias_e_notas"]), "mensagens": len(d["conversas"]),
            "whatsapp": len(d["whatsapp"].get("respostas", [])) if isinstance(d["whatsapp"], dict) else 0, "google": d["google"]["conectado"]}


def erase_all(user_id: str) -> dict:
    """Apaga os dados pessoais. Devolve o que foi apagado e os tokens do Google para revogar (feito pela rota)."""
    from src.jefrey.core.briefing import BriefingStore
    from src.jefrey.core.diary import DiaryStore
    from src.jefrey.core.google_oauth import delete_tokens
    from src.jefrey.core.history import HistoryStore
    from src.jefrey.core.learning import FactStore
    from src.jefrey.core.profile import ProfileStore
    from src.jefrey.core.reminders import ReminderStore
    from src.jefrey.core.studies import StudyStore
    from src.jefrey.core.wa_web import WAStore

    res: dict[str, Any] = {}
    res["fatos"] = _safe(lambda: FactStore().forget_all(user_id), 0)
    res["diario"] = _safe(lambda: DiaryStore().forget_all(user_id), 0)
    res["estudos"] = _safe(lambda: StudyStore().forget_all(user_id), 0)
    res["resumos"] = _safe(lambda: BriefingStore().forget_all(user_id), 0)
    res["whatsapp"] = _safe(lambda: WAStore().forget_all(user_id), 0)
    res["nome"] = _safe(lambda: (ProfileStore().clear_name(user_id), 1)[1], 0)

    def hist() -> int:
        h = HistoryStore()
        with h.engine.begin() as c:
            return c.execute(h.t.delete().where(h.t.c.user_id == user_id)).rowcount or 0

    res["mensagens"] = _safe(hist, 0)

    def reminders() -> int:
        s = ReminderStore()
        n = 0
        for r in s.pending(user_id):
            n += 1 if s.cancel(user_id, r["id"]) else 0
        return n

    res["lembretes"] = _safe(reminders, 0)

    def memories() -> int:
        from src.jefrey.core.memory import get_memory_manager

        lt = get_memory_manager().long_term
        n = 0
        for m in lt.list_recent(limit=100000, user_id=user_id):
            n += 1 if lt.delete(m["id"], user_id=user_id) else 0
        return n

    res["memorias"] = _safe(memories, 0)
    res["_google_tokens"] = _safe(lambda: delete_tokens(user_id), [])
    return res
