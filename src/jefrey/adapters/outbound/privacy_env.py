"""Onde moram os dados pessoais: cada metodo le ou apaga UM tipo de dado de UMA pessoa (imports na hora do uso)."""
from __future__ import annotations

from typing import Any


class PersonalData:
    # --- ler ---
    def name(self, uid: str):
        from src.jefrey.core.profile import ProfileStore

        return ProfileStore().get_name(uid)

    def facts(self, uid: str) -> list:
        from src.jefrey.core.learning import FactStore

        return FactStore().active(uid, 1000)

    def diary(self, uid: str) -> list:
        from src.jefrey.core.diary import DiaryStore

        return DiaryStore().recent(uid, 400)

    def studies(self, uid: str) -> list:
        from src.jefrey.core.studies import StudyStore

        st = StudyStore()
        return [{"title": t["title"], "level_label": t["level_label"], "body": (st.latest_guide(uid, t["id"]) or {}).get("body"),
                 "sources": (st.latest_guide(uid, t["id"]) or {}).get("sources", [])} for t in st.list_topics(uid)]

    def briefings(self, uid: str) -> list:
        from src.jefrey.core.briefing import BriefingStore

        return BriefingStore().all(uid)

    def reminders(self, uid: str) -> list:
        from src.jefrey.core.reminders import ReminderStore

        return ReminderStore().pending(uid)

    def memories(self, uid: str) -> list:
        from src.jefrey.core.memory import get_memory_manager

        return get_memory_manager().long_term.list_recent(limit=100000, user_id=uid)

    def conversation(self, uid: str) -> list:
        from src.jefrey.core.history import HistoryStore

        h = HistoryStore()
        with h.engine.connect() as c:
            rows = c.execute(h.t.select().where(h.t.c.user_id == uid).order_by(h.t.c.id)).fetchall()
        return [{"ts": r.ts.isoformat(), "role": r.role, "content": r.content} for r in rows]

    def whatsapp(self, uid: str) -> dict:
        from src.jefrey.core.wa_web import WAStore

        wa = WAStore()
        return {"chats": wa.list_chats(uid), "drafts": wa.list_drafts(uid, None, 500)}

    def google(self, uid: str) -> dict:
        from src.jefrey.core.google_oauth import status

        return status(uid)

    # --- apagar ---
    def forget_facts(self, uid: str) -> int:
        from src.jefrey.core.learning import FactStore

        return FactStore().forget_all(uid)

    def forget_diary(self, uid: str) -> int:
        from src.jefrey.core.diary import DiaryStore

        return DiaryStore().forget_all(uid)

    def forget_studies(self, uid: str) -> int:
        from src.jefrey.core.studies import StudyStore

        return StudyStore().forget_all(uid)

    def forget_briefings(self, uid: str) -> int:
        from src.jefrey.core.briefing import BriefingStore

        return BriefingStore().forget_all(uid)

    def forget_whatsapp(self, uid: str) -> int:
        from src.jefrey.core.wa_web import WAStore

        return WAStore().forget_all(uid)

    def forget_name(self, uid: str) -> int:
        from src.jefrey.core.profile import ProfileStore

        ProfileStore().clear_name(uid)
        return 1

    def forget_conversation(self, uid: str) -> int:
        from src.jefrey.core.history import HistoryStore

        h = HistoryStore()
        with h.engine.begin() as c:
            return c.execute(h.t.delete().where(h.t.c.user_id == uid)).rowcount or 0

    def cancel_reminders(self, uid: str) -> int:
        from src.jefrey.core.reminders import ReminderStore

        s = ReminderStore()
        return sum(1 for r in s.pending(uid) if s.cancel(uid, r["id"]))

    def forget_memories(self, uid: str) -> int:
        from src.jefrey.core.memory import get_memory_manager

        lt = get_memory_manager().long_term
        return sum(1 for m in lt.list_recent(limit=100000, user_id=uid) if lt.delete(m["id"], user_id=uid))

    def delete_google_tokens(self, uid: str) -> list:
        from src.jefrey.core.google_oauth import delete_tokens

        return delete_tokens(uid)


def register() -> None:
    from src.jefrey.ports import registry

    registry.default("personal_data", PersonalData)
