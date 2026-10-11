"""Atalho de compatibilidade do aprendizado: regras em domain/learning.py, ciclo em application/learning.py, banco em adapters/outbound/sql_facts.py."""
from typing import Any

from src.jefrey.adapters.outbound.sql_facts import FactStore, _now, _tables  # noqa: F401
from src.jefrey.application import learning as _app
from src.jefrey.application.learning import extract_by_llm  # noqa: F401
from src.jefrey.domain.learning import *  # noqa: F401,F403
from src.jefrey.domain.learning import _LLM_PROMPT, _clip, _norm, _plain, _validate  # noqa: F401


async def learn_from_turn(user_id: str, user_text: str, assistant_text: str, client: Any = None) -> dict:
    """Aprende com uma troca (ligacao padrao: banco SQL). Nunca levanta erro."""
    return await _app.learn_from_turn(user_id, user_text, assistant_text, client, store=FactStore())
