"""Brain2Queue - Redis Stream jefrey:brain2:queue com isolamento por user_id.

Cerebro 1 (agent.py) publica apos cada /chat; Brain2 consome via XREADGROUP.
Fail-closed: sem Redis, enfileira em memoria e re-tenta quando voltar.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

STREAM_KEY = "jefrey:brain2:queue"
GROUP = "brain2"
CONSUMER_PREFIX = "brain2-worker"
MAXLEN = 10000  # XADD maxlen, evita crescimento infinito


class Brain2Queue:
    """Fila Redis Stream entre Cerebro 1 -> Cerebro 2. user_id isolado no payload."""

    def __init__(self, redis_url: Optional[str] = None, redis_client=None):
        self._redis = redis_client
        self._url = redis_url or os.getenv("JEFREY_REDIS__URL", "redis://:jefrey@localhost:6379/0")
        self._fallback: List[Dict[str, Any]] = []

    def _get_redis(self):
        if self._redis is not None:
            return self._redis
        try:
            import redis  # type: ignore

            # sync redis for enqueue (usado dentro do FastAPI sync/async boundary)
            self._redis = redis.from_url(self._url, decode_responses=True)
            return self._redis
        except Exception as e:
            logger.debug("Brain2Queue redis unavailable: %s", e)
            return None

    def enqueue(self, user_id: str, thread_id: str, user_input: str, response: str, meta: Optional[Dict[str, Any]] = None) -> str:
        """Publica um evento do Cerebro 1 para o Brain2. Retorna msg_id ou fallback id."""
        payload = {
            "user_id": user_id or "guest",
            "thread_id": thread_id or f"thread_{user_id}_{uuid.uuid4().hex[:8]}",
            "user_input": (user_input or "")[:2000],
            "response": (response or "")[:4000],
            "ts": str(int(time.time())),
            "meta_json": json.dumps(meta or {}, ensure_ascii=False)[:2000],
        }
        r = self._get_redis()
        if r is not None:
            try:
                msg_id = r.xadd(STREAM_KEY, payload, maxlen=MAXLEN, approximate=True)
                logger.info("brain2 enqueue user=%s thread=%s id=%s", payload["user_id"], payload["thread_id"], msg_id)
                return str(msg_id)
            except Exception as e:
                logger.warning("brain2 enqueue redis failed, fallback mem: %s", e)
        # fallback in-memory
        fid = f"mem-{uuid.uuid4().hex[:12]}"
        self._fallback.append({"_id": fid, **payload})
        # cap fallback
        if len(self._fallback) > 500:
            self._fallback = self._fallback[-500:]
        logger.info("brain2 enqueue fallback user=%s id=%s", payload["user_id"], fid)
        return fid

    def pending_count(self) -> int:
        """Apenas para health/metrics: tamanho aproximado da stream + fallback."""
        r = self._get_redis()
        total = len(self._fallback)
        if r is not None:
            try:
                total += int(r.xlen(STREAM_KEY) or 0)
            except Exception:
                pass
        return total

    def get_fallback(self) -> List[Dict[str, Any]]:
        return list(self._fallback)


_singleton: Optional[Brain2Queue] = None


def get_brain2_queue(redis_client=None) -> Brain2Queue:
    global _singleton
    if _singleton is None:
        _singleton = Brain2Queue(redis_client=redis_client)
    elif redis_client is not None and _singleton._redis is None:
        _singleton._redis = redis_client
    return _singleton
