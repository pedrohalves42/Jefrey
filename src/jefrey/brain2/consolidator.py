"""Consolidator - episodic -> semantic a cada 5min (DIFF3 esqueleto)."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class Consolidator:
    """Consolida dialogos episodicos em memoria semantica (pgvector).

    Esqueleto DIFF3: loga e conta; persistencia real via MemoryManager quando houver Ollama.
    """

    def __init__(self):
        self.consolidations = 0

    async def consolidate(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Recebe um evento do Brain2Queue e consolida."""
        user_id = event.get("user_id", "guest")
        thread_id = event.get("thread_id", "")
        self.consolidations += 1
        logger.info("brain2 consolidator user=%s thread=%s n=%d", user_id, thread_id, self.consolidations)
        # TODO: chamar MemoryManager.add_semantic / embeddings quando embeddings estiver estavel
        # Por enquanto apenas sinaliza que o evento foi visto pelo Brain2
        return {"status": "consolidated", "user_id": user_id, "thread_id": thread_id, "n": self.consolidations}
