"""
CIPHER-033: EventBus Subscriber — HMAC verify + Redis Streams XREADGROUP (P4-03).

Per-tenant topic jefrey.events.{user_id}.{tool_name} (Axiom #2).
Fail-closed: assinatura inválida => DLQ (memória em dev, XADD jefrey:dlq:{user_id} em prod).
P4-03: XREADGROUP com consumer group jefrey.{tool} + idempotência via {user_id, id} Streams.
Compat: handle_message(signed_dict) permanece para tests unitários sem Redis.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from src.jefrey.eventbus.signing import _canonical_json, verify_message

logger = logging.getLogger(__name__)


class EventBusSubscriber:
    """Subscriber verify + Streams. handle_message é unit-testável sem Redis."""

    def __init__(self, hmac_key: Optional[str] = None, dead_letter=None, redis_url: Optional[str] = None):
        self.hmac_key = hmac_key
        self.dead_letter = dead_letter if dead_letter is not None else []
        self._handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {}
        self._redis_url = redis_url
        self._redis = None

    def _is_prod(self) -> bool:
        return os.getenv("JEFREY_ENV", "dev") == "prod"

    def _get_redis(self):
        if self._redis is not None:
            return self._redis
        url = self._redis_url or os.getenv("JEFREY_REDIS__URL", "redis://localhost:6379/0")
        try:
            import redis as redis_sync

            r = redis_sync.from_url(url, socket_connect_timeout=2, socket_timeout=2)
            r.ping()
            self._redis = r
            return r
        except Exception as e:
            self._redis = None
            raise RuntimeError(f"Redis indisponível para EventBus subscribe (fail-closed): {e}") from e

    def _dlq_add(self, message: Dict[str, Any], reason: str):
        # memória sempre
        self.dead_letter.append(
            {
                "message": message,
                "error": reason,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
        )
        # em prod também XADD se Redis disponível (best-effort)
        try:
            user_id = message.get("user_id") or "unknown"
            r = self._get_redis()
            r.xadd(f"jefrey:dlq:{user_id}", {"data": _canonical_json(message), "reason": reason}, maxlen=5000, approximate=True)
        except Exception as e:
            logger.debug("DLQ XADD falhou (best-effort): %s", e)

    def subscribe(
        self,
        tool_name: str,
        action: str,
        user_id: str,
        handler: Callable[[Dict[str, Any]], None],
    ) -> None:
        topic_key = tool_name + ":" + action + ":" + user_id
        self._handlers[topic_key] = handler

    def set_dead_letter(self, dlq):
        self.dead_letter = dlq

    def handle_message(self, raw_message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Verifica HMAC + roteia para handler por user_id/tool_name/action."""
        is_valid, error_reason = verify_message(raw_message, self.hmac_key)
        if not is_valid:
            self._dlq_add(raw_message, error_reason or "invalid_signature")
            return None
        msg_user_id = raw_message.get("user_id")
        if not msg_user_id:
            self._dlq_add(raw_message, "missing_user_id")
            return None
        tool_name = raw_message.get("tool_name", "")
        action = raw_message.get("action", "")
        topic_key = tool_name + ":" + action + ":" + msg_user_id
        handler = self._handlers.get(topic_key)
        if handler is None:
            self._dlq_add(raw_message, "no_handler_for_" + topic_key)
            return None
        try:
            handler(raw_message)
            return raw_message
        except Exception as e:
            self._dlq_add(raw_message, "handler_error: " + str(e))
            return None

    def get_dead_letter(self) -> List[Dict[str, Any]]:
        return self.dead_letter

    # P4-03: Streams helpers (opcional, prod)
    def ensure_consumer_group(self, topic: str, group: str = "jefrey"):
        """Cria consumer group se não existir (idempotente)."""
        r = self._get_redis()
        try:
            r.xgroup_create(topic, group, id="0", mkstream=True)
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                raise

    def xread_group(self, topics: List[str], group: str = "jefrey", consumer: str = "worker-1", count: int = 10, block_ms: int = 2000):
        """XREADGROUP para consumo em workers; retorna lista de (topic, [(id, fields)])."""
        r = self._get_redis()
        streams = {t: ">" for t in topics}
        return r.xreadgroup(group, consumer, streams, count=count, block=block_ms)
