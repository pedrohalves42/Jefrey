"""Reflector - LLM-as-judge reavalia respostas via content_guard - esqueleto DIFF3."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class Reflector:
    """Reavalia a resposta do Cerebro 1 com content_guard + heuristica LLM.

    Esqueleto DIFF3: sem chamada LLM ainda; marca como reviewed e aplica guard.
    """

    def __init__(self):
        self.reviews = 0

    async def review(self, event: Dict[str, Any]) -> Dict[str, Any]:
        user_id = event.get("user_id", "guest")
        response = event.get("response", "")
        self.reviews += 1
        # usa content_guard para detectar prompt injection / vazamento
        verdict = "ok"
        reason = ""
        try:
            from src.jefrey.core.content_guard import sanitize_tool_output

            sanitized = sanitize_tool_output(response, tool_name="brain2.reflector")
            if sanitized != response:
                verdict = "sanitized"
                reason = "content_guard sanitizou trecho suspeito"
        except Exception as e:
            logger.debug("reflector guard failed: %s", e)
        # heuristica qwen leak
        if "Qwen" in response or "Alibaba" in response:
            verdict = "leak"
            reason = "vazamento identidade Qwen/Alibaba detectado - blindagem system_prompt recomendada"
        logger.info("brain2 reflector user=%s verdict=%s n=%d", user_id, verdict, self.reviews)
        return {"status": "reviewed", "user_id": user_id, "verdict": verdict, "reason": reason, "n": self.reviews}
