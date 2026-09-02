"""Rate limiting per user_id/tool_name using Redis token bucket — fail-closed (CIPHER-026).

Axiom #6: sem Redis => deny/raise, nunca allow. Pipeline incr+expire atomico, sem delete.
DDIA: pool_pre_ping + retry. Observabilidade: RATE_LIMIT_TOTAL sem user_id label.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter stored in Redis — fail-closed."""

    def __init__(self, redis_url: str | None = None):
        if redis_url is None:
            try:
                from src.jefrey.core.config import get_settings

                redis_url = get_settings().redis.dsn
            except Exception:
                redis_url = os.getenv("JEFREY_REDIS__URL", "redis://localhost:6379/0")
        self.redis_url = redis_url
        self._redis = None
        self._redis_sync = None

    async def _get_redis(self):
        if self._redis is None:
            try:
                import redis.asyncio as redis

                self._redis = redis.from_url(
                    self.redis_url, socket_connect_timeout=2, socket_timeout=2
                )
                await self._redis.ping()
            except Exception as e:
                self._redis = None
                logger.error("rate_limit: Redis indisponivel (fail-closed deny): %s", e)
                raise RuntimeError(f"Redis indisponivel para rate limit (fail-closed): {e}") from e
        return self._redis

    def _get_redis_sync(self):
        if self._redis_sync is None:
            try:
                import redis as redis_sync

                self._redis_sync = redis_sync.from_url(
                    self.redis_url, socket_connect_timeout=2, socket_timeout=2
                )
                self._redis_sync.ping()
            except Exception as e:
                self._redis_sync = None
                logger.error("rate_limit: Redis sync indisponivel (fail-closed deny): %s", e)
                raise RuntimeError(f"Redis indisponivel para rate limit sync (fail-closed): {e}") from e
        return self._redis_sync

    async def is_allowed(self, user_id: str, tool_name: str, rate: int = 60, burst: int = 20) -> str:
        """Fail-closed: sem user_id => deny, sem Redis => RuntimeError/deny, pipeline atomico."""
        if not user_id:
            logger.warning("rate_limit: user_id ausente => deny (Axiom #2)")
            try:
                from src.jefrey.core.metrics import RATE_LIMIT_TOTAL

                RATE_LIMIT_TOTAL.labels(tool_name=tool_name, decision="deny").inc()
            except Exception as _e:
                logger.debug("rate_limit metrics inc falhou: %s", _e)
            return "deny"
        redis = await self._get_redis()
        key = f"rate:{user_id}:{tool_name}"
        try:
            pipe = redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, 60)
            pipe.ttl(key)
            results = await pipe.execute()
            count = int(results[0])
            if results[2] == -1:
                await redis.expire(key, 60)
            decision = "deny" if count > rate else "allow"
            try:
                from src.jefrey.core.metrics import RATE_LIMIT_TOTAL

                RATE_LIMIT_TOTAL.labels(tool_name=tool_name, decision=decision).inc()
            except Exception as _e:
                logger.debug("rate_limit metrics inc falhou: %s", _e)
            return decision
        except RuntimeError:
            raise
        except Exception as e:
            logger.error("rate_limit: erro pipeline (fail-closed deny): %s", e)
            try:
                from src.jefrey.core.metrics import RATE_LIMIT_TOTAL

                RATE_LIMIT_TOTAL.labels(tool_name=tool_name, decision="deny").inc()
            except Exception as _e:
                logger.debug("rate_limit metrics inc falhou: %s", _e)
            return "deny"

    def is_allowed_sync(self, user_id: str, tool_name: str, rate: int = 60, burst: int = 20) -> str:
        """Sync wrapper para PolicyEngine.decide (sync) — nao quebrar assinatura."""
        if not user_id:
            logger.warning("rate_limit: user_id ausente => deny (Axiom #2) [sync]")
            try:
                from src.jefrey.core.metrics import RATE_LIMIT_TOTAL

                RATE_LIMIT_TOTAL.labels(tool_name=tool_name, decision="deny").inc()
            except Exception as _e:
                logger.debug("rate_limit metrics inc falhou: %s", _e)
            return "deny"
        redis = self._get_redis_sync()
        key = f"rate:{user_id}:{tool_name}"
        try:
            pipe = redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, 60)
            pipe.ttl(key)
            results = pipe.execute()
            count = int(results[0])
            if results[2] == -1:
                redis.expire(key, 60)
            decision = "deny" if count > rate else "allow"
            try:
                from src.jefrey.core.metrics import RATE_LIMIT_TOTAL

                RATE_LIMIT_TOTAL.labels(tool_name=tool_name, decision=decision).inc()
            except Exception as _e:
                logger.debug("rate_limit metrics inc falhou: %s", _e)
            return decision
        except RuntimeError:
            raise
        except Exception as e:
            logger.error("rate_limit: erro pipeline sync (fail-closed deny): %s", e)
            try:
                from src.jefrey.core.metrics import RATE_LIMIT_TOTAL

                RATE_LIMIT_TOTAL.labels(tool_name=tool_name, decision="deny").inc()
            except Exception as _e:
                logger.debug("rate_limit metrics inc falhou: %s", _e)
            return "deny"

    async def is_allowed_or_raise(self, user_id: str, tool_name: str, rate: int = 60) -> None:
        dec = await self.is_allowed(user_id, tool_name, rate)
        if dec == "deny":
            from fastapi import HTTPException

            raise HTTPException(status_code=429, detail="rate limit exceeded")


_RATE_LIMITER: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _RATE_LIMITER
    if _RATE_LIMITER is None:
        _RATE_LIMITER = RateLimiter()
    return _RATE_LIMITER
