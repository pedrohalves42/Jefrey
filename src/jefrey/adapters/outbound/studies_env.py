"""O que os estudos usam do mundo de fora: o banco dos estudos, leitura da web, fatos, historico, memoria e o modelo.
Imports na hora do uso (pelos nomes `core.*`), para os testes poderem trocar uma peca so."""
from __future__ import annotations

from typing import Any


class StudiesEnvironment:
    def store(self) -> Any:
        from src.jefrey.adapters.outbound.sql_studies import StudyStore

        return StudyStore()

    # --- web ---
    async def web_search(self, query: str, n: int = 6) -> list:
        from src.jefrey.core import webread

        return await webread.web_search(query, n)

    async def fetch_page(self, url: str) -> dict:
        from src.jefrey.core import webread

        return await webread.fetch_page(url)

    def domain(self, url: str) -> str:
        from src.jefrey.core import webread

        return webread.domain(url)

    @property
    def read_error(self):
        from src.jefrey.core import webread

        return webread.ReadError

    # --- o que se sabe da pessoa ---
    def active_facts(self, user_id: str) -> list:
        from src.jefrey.core.learning import FactStore

        return FactStore().active(user_id, 200)

    def recent_user_messages(self, user_id: str, n: int) -> "list[str]":
        from src.jefrey.core.history import HistoryStore

        h = HistoryStore()
        with h.engine.connect() as c:
            rows = c.execute(h.t.select().where((h.t.c.user_id == user_id) & (h.t.c.role == "user")).order_by(h.t.c.id.desc()).limit(n)).fetchall()
        return [r.content for r in rows]

    def save_note_and_learn(self, user_id: str, text: str) -> int:
        """Guarda o texto nas memorias e tira dele fatos (nunca segredos). Devolve quantos fatos novos."""
        from src.jefrey.core.learning import FactStore, extract_by_rules
        from src.jefrey.core.memory import get_memory_manager

        get_memory_manager().long_term.add(text[:4000], metadata={"type": "note", "source": "aprender"}, user_id=user_id)
        fs, n = FactStore(), 0
        if fs.enabled(user_id):
            for f in extract_by_rules(text):
                if fs.learn(user_id, f) != "same":
                    n += 1
        return n

    def candidate_users(self, store: Any = None) -> "list[str]":
        from sqlalchemy import select

        from src.jefrey.core.learning import _tables as learning_tables

        store = store or self.store()
        facts, _ = learning_tables()
        facts.create(store.engine, checkfirst=True)
        with store.engine.connect() as c:
            ids = {r[0] for r in c.execute(select(store.topics.c.user_id).distinct())}
            ids |= {r[0] for r in c.execute(select(facts.c.user_id).distinct())}
        return sorted(u for u in ids if u and u not in ("system", "anonymous"))

    # --- ritmo e modelo ---
    def busy(self, user_id: str, what: str, detail: str = ""):
        from src.jefrey.core import activity

        return activity.busy(user_id, what, detail)

    def idle_seconds(self, user_id: str) -> float:
        from src.jefrey.core import activity

        return activity.idle_seconds(user_id)

    def llm_client(self) -> Any:
        from src.jefrey.core.llm_provider import get_llm_client

        return get_llm_client()


def register() -> None:
    from src.jefrey.ports import registry

    registry.default("studies_env", StudiesEnvironment)
