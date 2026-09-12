"""Planner - sugestoes proativas (agenda/email) - esqueleto DIFF3."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class Planner:
    """Gera sugestoes proativas baseadas no historico do usuario (esqueleto)."""

    def __init__(self):
        self.plans = 0

    async def plan(self, event: Dict[str, Any]) -> Dict[str, Any]:
        user_id = event.get("user_id", "guest")
        self.plans += 1
        logger.info("brain2 planner user=%s n=%d input=%.80s", user_id, self.plans, event.get("user_input", ""))
        # TODO: integrar skills/calendar + LLM planner com Ollama qwen2.5:0.5b
        suggestions: List[str] = []
        # heuristica minima: se menciona reuniao/amanha, sugere checar calendario
        text = (event.get("user_input") or "").lower()
        if any(k in text for k in ["reuniao", "reunião", "amanha", "amanhã", "agenda", "calendario"]):
            suggestions.append("Quer que eu verifique sua agenda para amanha?")
        return {"status": "planned", "user_id": user_id, "suggestions": suggestions, "n": self.plans}
