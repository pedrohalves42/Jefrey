"""Caso de uso: aprender com uma troca de conversa. Usa so portas (modelo de IA e armazenamento); nunca levanta erro."""
from __future__ import annotations

from src.jefrey.domain.llm_roles import chat_as

import logging
from typing import Any

from src.jefrey.application import activity
from src.jefrey.domain.learning import Fact, _LLM_PROMPT, _validate, extract_by_rules, has_secret, parse_llm_facts, worth_learning
from src.jefrey.ports import FactsPort

logger = logging.getLogger(__name__)


async def extract_by_llm(client: Any, user_text: str, assistant_text: str) -> list[Fact]:
    messages = [
        {"role": "system", "content": _LLM_PROMPT},
        {"role": "user", "content": f"<usuario>\n{user_text[:1500]}\n</usuario>\n<assistente>\n{assistant_text[:800]}\n</assistente>"},
    ]
    try:
        return parse_llm_facts(await chat_as(client, messages, "resumo"))
    except Exception as e:
        logger.info("extracao por IA indisponivel (%s)", type(e).__name__)
        return []


async def learn_from_turn(user_id: str, user_text: str, assistant_text: str, client: Any = None, *, store: FactsPort) -> dict:
    """Aprende com uma troca. Nunca levanta erro (roda em segundo plano). Devolve contagens para teste/registro."""
    with activity.busy(user_id, "aprendendo"):  # a tela mostra "aprendendo..." no avatar
        return await _learn(user_id, user_text, assistant_text, client, store)


async def _learn(user_id: str, user_text: str, assistant_text: str, client: Any, store: FactsPort) -> dict:
    result = {"new": 0, "updated": 0, "same": 0, "skipped": 0}
    try:
        if not store.enabled(user_id) or not worth_learning(user_text) or has_secret(user_text) and not extract_by_rules(user_text):
            result["skipped"] = 1
            return result
        facts = extract_by_rules(user_text)
        if client is not None and getattr(getattr(client, "config", None), "is_cloud", False):
            known = {(f.kind, f.key) for f in facts}
            facts += [f for f in await extract_by_llm(client, user_text, assistant_text) if (f.kind, f.key) not in known]
            facts = _validate(facts)
        for f in facts:
            result[store.learn(user_id, f)] += 1
    except Exception as e:  # aprender nunca pode derrubar a conversa
        logger.warning("aprendizado falhou: %s", type(e).__name__)
    return result
