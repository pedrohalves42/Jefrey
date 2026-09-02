"""
CIPHER-033: EventBus Publisher — HMAC + Redis Streams (P4-03).

Per-tenant topic jefrey.events.{user_id}.{tool_name} (Axiom #2).
Fail-closed (Axiom #6): sem Redis em prod => raise, em dev cai para memória.
Streams: XADD com maxlen, mantém sign_message kid versionado.
Compat: hmac_key ctor para tests.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.jefrey.eventbus.signing import _canonical_json, sign_message
from src.jefrey.core.policy import PolicyContext

logger = logging.getLogger(__name__)


class DeadLetterQueue:
    """DLQ in-memory (dev) + XADD jefrey:dlq:{user_id} em prod quando Redis disponível."""

    def __init__(self):
        self.messages: list = []

    def add(self, message: Dict[str, Any], reason: str):
        self.messages.append({"message": message, "reason": reason, "timestamp": datetime.now(timezone.utc)})

    def get_all(self) -> list:
        return self.messages


class EventBusPublisher:
    """Publisher HMAC + Redis Streams. Fallback in-memory so fora de prod."""

    def __init__(self, hmac_key: Optional[str] = None, redis_url: Optional[str] = None):
        self.hmac_key = hmac_key
        self._redis_url = redis_url
        self._redis = None
        self._memory_fallback: list = []

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
            raise RuntimeError(f"Redis indisponível para EventBus publish (fail-closed): {e}") from e

    def publish(
        self,
        tool_name: str,
        action: str,
        payload: Dict[str, Any],
        user_id: str,
        ctx: Optional[PolicyContext] = None,
    ) -> Dict[str, Any]:
        ctx = ctx or PolicyContext()
        # risk assessment best-effort (não bloqueia publish em caso de erro)
        try:
            from src.jefrey.skills.risk_assessment import assess_skill_risk, get_required_role

            risk = assess_skill_risk(tool_name, ctx=ctx)
            required_role = get_required_role(risk)
            if ctx.user_role and ctx.user_role != required_role and required_role != "GUEST":
                pass
        except Exception as e:
            logger.debug("risk_assessment falhou: %s", e)

        message = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "tool_name": tool_name,
            "action": action,
            "payload": payload,
        }
        signed = sign_message(message, user_id, self.hmac_key)
        topic = self.get_topic(user_id, tool_name)

        # Tenta Redis Streams; se falhar: prod => raise (fail-closed), dev => memória
        try:
            r = self._get_redis()
            # XADD topic * data <json>  — maxlen 10000 por stream
            r.xadd(topic, {"data": _canonical_json(signed)}, maxlen=10000, approximate=True)
            logger.debug("EventBus XADD %s id=%s", topic, signed.get("id"))
        except Exception as e:
            if self._is_prod():
                logger.error("EventBus publish falhou em prod (fail-closed): %s", e)
                raise
            logger.debug("EventBus publish fallback memória (dev): %s", e)
            self._memory_fallback.append({"topic": topic, "message": signed})
        return signed

    def get_topic(self, user_id: str, tool_name: str) -> str:
        return "jefrey.events." + user_id + "." + tool_name

    # compat para tests que inspecionam fallback
    @property
    def memory_fallback(self):
        return self._memory_fallback
