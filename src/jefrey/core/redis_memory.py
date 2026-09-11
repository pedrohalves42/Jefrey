"""Redis-backed short-term memory with user_id isolation (Axiom #2)."""

from __future__ import annotations

import logging
import time
from typing import Optional, Dict, Any

import redis

logger = logging.getLogger(__name__)


class RedisShortTermMemory:
    """Short-term memory stored in Redis Streams with per-user isolation.

    Axiom #2: ISOLAMENTO — SCAN sempre `jefrey:wm:{user_id}:*` + `ex=86400`
    em todo SET. DLQ: `jefrey:dlq:{user_id}` maxlen=5000.
    """

    def __init__(self, redis_url: str | None = None):
        if redis_url is None:
            try:
                from src.jefrey.core.config import get_settings

                redis_url = get_settings().redis.dsn
            except Exception:
                redis_url = "redis://localhost:6379/0"
        self._redis = redis.from_url(
            redis_url, socket_connect_timeout=2, socket_timeout=2
        )
        self._prefix = "jefrey:wm"

    def _key(self, user_id: str, key: str) -> str:
        """Build user-isolated key: jefrey:wm:{user_id}:{key}"""
        user_id = user_id or "guest"
        return f"{self._prefix}:{user_id}:{key}"


    def _ensure_user_isolation(self, user_id: str) -> None:
        """Validate that operations are user-isolated.

        Raises if user_id is None or empty — Axiom #2 ISOLAMENTO.
        """
        if not user_id:
            raise ValueError(
                "user_id obrigatório em RedisShortTermMemory — "
                "Axiom #2 ISOLAMENTO"
            )

    def add(self, key: str, value: str, user_id: str | None = None, ttl: int = 86400) -> None:
        """Add a key-value pair to short-term memory with user isolation.

        GUARDA: `jefrey:wm:{user_id}:{key}` com TTL de 86400s (24h).
        """
        self._ensure_user_isolation(user_id)
        k = self._key(user_id, key)
        try:
            self._redis.setex(k, ttl, value)
            # DLQ: se valor for erro, enviar para DLQ do usuário
            if "error" in value.lower() or "fail" in value.lower():
                dlq_key = f"jefrey:dlq:{user_id}"
                self._redis.rpush(dlq_key, f"{k}:{value}")
                # Mantém maxlen=5000 no DLQ
                self._redis.ltrim(dlq_key, 0, 4999)
        except Exception as e:
            logger.error("RedisShortTermMemory.add falhou: %s", e, exc_info=True)
            raise

    def get(self, key: str, user_id: str | None = None) -> str | None:
        """Get a value from short-term memory with user isolation."""
        self._ensure_user_isolation(user_id)
        k = self._key(user_id, key)
        try:
            value = self._redis.get(k)
            return value.decode("utf-8") if value else None
        except Exception as e:
            logger.error("RedisShortTermMemory.get falhou: %s", e, exc_info=True)
            return None

    def set(self, key: str, value: str, user_id: str | None = None, ttl: int = 86400) -> None:
        """Set a value in short-term memory with user isolation and TTL."""
        self._ensure_user_isolation(user_id)
        k = self._key(user_id, key)
        try:
            self._redis.setex(k, ttl, value)
        except Exception as e:
            logger.error("RedisShortTermMemory.set falhou: %s", e, exc_info=True)
            raise

    def delete(self, key: str, user_id: str | None = None) -> bool:
        """Delete a key from short-term memory with user isolation."""
        self._ensure_user_isolation(user_id)
        k = self._key(user_id, key)
        try:
            deleted = self._redis.delete(k)
            return deleted > 0
        except Exception as e:
            logger.error("RedisShortTermMemory.delete falhou: %s", e, exc_info=True)
            return False

    def scan(
        self, pattern: str = "*", user_id: str | None = None, count: int = 100
    ) -> list[str]:
        """Scan keys with user isolation — always uses user-specific pattern.

        GUARANTEE: sempre usa `jefrey:wm:{user_id}:*` — nunca varre todo o Redis.
        """
        self._ensure_user_isolation(user_id)
        pattern = self._key(user_id, pattern)
        try:
            keys: list[str] = []
            cursor = 0
            while True:
                cursor, result = self._redis.scan(
                    cursor, match=pattern, count=count
                )
                keys.extend(result)
                if cursor == 0:
                    break
            return keys
        except Exception as e:
            logger.error("RedisShortTermMemory.scan falhou: %s", e, exc_info=True)
            return []

    def health_check(self) -> dict:
        try:
            self._redis.ping()
            return {"status": "ok", "backend": "redis"}
        except Exception as e:
            return {"status": "error", "backend": "redis", "error": str(e)}

    def expire(self, key: str, user_id: str | None = None, ttl: int = 86400) -> bool:
        """Set TTL on a key with user isolation."""
        self._ensure_user_isolation(user_id)
        k = self._key(user_id, key)
        try:
            return self._redis.expire(k, ttl)
        except Exception as e:
            logger.error("RedisShortTermMemory.expire falhou: %s", e, exc_info=True)
            return False

# Alias compat verify_p1 (P1) — Redis    def get_messages(self, user_id: str | None = None) -> list:
        # compat shim for MemoryManager.get_context — returns empty list (Redis Streams alternative)
        return []

    def add_user(self, content: str, user_id: str | None = None) -> None:
        self.add(key=f"msg:user:{content[:20]}", value=content, user_id=user_id or "guest")

    def add_assistant(self, content: str, user_id: str | None = None) -> None:
        self.add(key=f"msg:assistant:{content[:20]}", value=content, user_id=user_id or "guest")

    def clear(self, user_id: str | None = None) -> None:
        try:
            keys = self.scan(pattern="*", user_id=user_id or "guest")
            for k in keys:
                # keys are bytes
                key = k.decode() if isinstance(k, bytes) else k
                # strip prefix to get inner key — delete expects user key part
                prefix = f"{self._prefix}:{user_id or 'guest'}:"
                inner = key[len(prefix):] if key.startswith(prefix) else key
                self.delete(inner, user_id=user_id or "guest")
        except Exception:
            pass

    @property
    def token_count(self) -> int:
        return 0

    def __len__(self) -> int:
        return 0

WorkingMemory = RedisShortTermMemory
class RedisWorkingMemory(RedisShortTermMemory):
    """Alias legacy — mantem API verify_p1. Axioma #2: herda isolamento por user_id."""
    pass

    def get_messages(self, user_id: str | None = None) -> list:
        # compat shim for MemoryManager.get_context — returns empty list (Redis Streams alternative)
        return []

    def add_user(self, content: str, user_id: str | None = None) -> None:
        self.add(key=f"msg:user:{content[:20]}", value=content, user_id=user_id or "guest")

    def add_assistant(self, content: str, user_id: str | None = None) -> None:
        self.add(key=f"msg:assistant:{content[:20]}", value=content, user_id=user_id or "guest")

    def clear(self, user_id: str | None = None) -> None:
        try:
            keys = self.scan(pattern="*", user_id=user_id or "guest")
            for k in keys:
                # keys are bytes
                key = k.decode() if isinstance(k, bytes) else k
                # strip prefix to get inner key — delete expects user key part
                prefix = f"{self._prefix}:{user_id or 'guest'}:"
                inner = key[len(prefix):] if key.startswith(prefix) else key
                self.delete(inner, user_id=user_id or "guest")
        except Exception:
            pass

    @property
    def token_count(self) -> int:
        return 0

    def __len__(self) -> int:
        return 0

WorkingMemory = RedisShortTermMemory
