"""Tudo que o agente (application/agent.py) usa do mundo de fora: historico, perfil, fatos, diario, estudos, ferramentas e modelo.

Os imports sao feitos na hora do uso (e pelos nomes dos modulos `core.*`): assim os testes continuam trocando uma peca so
e uma peca fora do ar nunca impede o Jefrey de partir.
"""
from __future__ import annotations

import asyncio
from typing import Any

_tasks: set = set()  # referencias das tarefas em segundo plano (sem isso o Python pode descarta-las no meio)


def _later(coro) -> None:
    task = asyncio.get_running_loop().create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


class AgentEnvironment:
    # --- pecas de governanca (o agente aceita outras no construtor) ---
    def rate_limiter(self) -> Any:
        from src.jefrey.core.rate_limit import RateLimiter

        return RateLimiter()

    def hitl_manager(self) -> Any:
        from src.jefrey.core.hitl import HITLManager

        return HITLManager()

    def rbac(self) -> Any:
        from src.jefrey.core.rbac import RBAC

        return RBAC()

    def audit_logger(self) -> Any:
        from src.jefrey.core.audit import get_audit_logger

        return get_audit_logger()

    def memory(self) -> Any:
        from src.jefrey.core.memory import MemoryManager

        return MemoryManager()

    def resolve_role(self, preferred=None) -> Any:
        from src.jefrey.core.rbac import resolve_role

        return resolve_role(preferred)

    # --- conversa ---
    def history_load(self, user_id: str, thread_id: str, limit: int) -> list:
        from src.jefrey.core.history import HistoryStore

        return HistoryStore().load(user_id, thread_id, limit)

    def history_add(self, user_id: str, thread_id: str, user_input: str, answer: str) -> None:
        from src.jefrey.core.history import HistoryStore

        HistoryStore().add_turn(user_id, thread_id, user_input, answer)

    # --- o que se sabe da pessoa ---
    def person_name(self, user_id: str, user_input: str) -> "str | None":
        from src.jefrey.core.profile import ProfileStore, detect_name

        store = ProfileStore()
        told = detect_name(user_input)
        return store.set_name(user_id, told) if told else store.get_name(user_id)

    def profile_lines(self, user_id: str) -> list:
        from src.jefrey.core.learning import FactStore

        return FactStore().profile_lines(user_id)

    def plain_facts(self, user_id: str) -> list:
        from src.jefrey.core.learning import FactStore

        store = FactStore()
        return [f["text"] for f in store.active(user_id, 200) if not f["sensitive"]] if store.enabled(user_id) else []

    def diary_recent(self, user_id: str, n: int) -> list:
        from src.jefrey.core.diary import DiaryStore

        return DiaryStore().recent(user_id, n)

    def study_lines(self, user_id: str, user_input: str) -> list:
        from src.jefrey.core import studies

        return studies.guide_lines(user_id, user_input)

    def touch_activity(self, user_id: str) -> None:
        from src.jefrey.core import activity

        activity.touch(user_id)

    # --- aprender em segundo plano ---
    def schedule_diary(self, user_id: str, tz: Any) -> None:
        from src.jefrey.core.diary import catch_up
        from src.jefrey.core.llm_provider import get_llm_client

        _later(catch_up(user_id, tz, get_llm_client()))

    def schedule_learning(self, user_id: str, user_input: str, answer: str) -> None:
        from src.jefrey.core.learning import learn_from_turn
        from src.jefrey.core.llm_provider import get_llm_client

        _later(learn_from_turn(user_id, user_input, answer, get_llm_client()))

    # --- ferramentas e modelo ---
    def load_tools(self, user_id: str) -> "tuple[dict, dict]":
        from src.jefrey.core.availability import unavailable_skills
        from src.jefrey.core.skill_prefs import enabled_tools
        from src.jefrey.domain.tool_catalog import CATALOG
        from src.jefrey.skills import load_skills, skill_registry

        load_skills()
        skills = [skill_registry.get_skill(m.name) for m in skill_registry.list_skills()]
        unavailable = unavailable_skills(user_id)
        return enabled_tools([sk for sk in skills if sk], CATALOG, set(unavailable)), unavailable

    def llm_client(self) -> Any:
        from src.jefrey.core.llm_provider import get_llm_client

        return get_llm_client()

    def model_info(self) -> "tuple[str, str, bool]":
        from src.jefrey.core.llm_provider import config_from_settings

        cfg = config_from_settings()
        return cfg.model, cfg.provider, cfg.is_cloud

    def friendly_error(self, e: Exception) -> str:
        from src.jefrey.core.llm_provider import friendly_error

        return friendly_error(e)


def register() -> None:
    from src.jefrey.ports import registry

    registry.default("agent_env", AgentEnvironment)

