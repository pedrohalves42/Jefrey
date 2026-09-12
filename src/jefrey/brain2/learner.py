"""Learner - thumbs up/down ajusta top_k/similarity_threshold per user_id - esqueleto DIFF3."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class Learner:
    """Aprende preferencias por usuario (esqueleto; persiste em Redis quando disponivel)."""

    def __init__(self):
        self.feedbacks = 0
        self._prefs: Dict[str, Dict[str, Any]] = {}

    async def learn(self, event: Dict[str, Any], feedback: str = "implicit") -> Dict[str, Any]:
        user_id = event.get("user_id", "guest")
        self.feedbacks += 1
        # feedback: thumbs_up / thumbs_down / implicit
        pref = self._prefs.setdefault(user_id, {"top_k": 5, "threshold": 0.7, "ups": 0, "downs": 0})
        if feedback == "thumbs_up":
            pref["ups"] += 1
        elif feedback == "thumbs_down":
            pref["downs"] += 1
        logger.info("brain2 learner user=%s feedback=%s n=%d prefs=%s", user_id, feedback, self.feedbacks, pref)
        return {"status": "learned", "user_id": user_id, "feedback": feedback, "prefs": dict(pref), "n": self.feedbacks}

    def get_prefs(self, user_id: str) -> Dict[str, Any]:
        return dict(self._prefs.get(user_id, {"top_k": 5, "threshold": 0.7, "ups": 0, "downs": 0}))
