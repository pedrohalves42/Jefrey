"""P1.2 E1 -- Rate-Limit distribuido com Redis Lua (ZSET) + fallback local.

AXIOM: codigo tipado (TypedDict/Final/Literal), teste reproduzivel, fail-open
       degradado para rate-limit (distinto de fail-closed para auth/HITL).
CIPHER-025: observabilidade via Counter jefrey_rate_limit_total{tool_name,decision}.
Livros: High Performance Python (ZSET O(log N) + EXPIRE atomico),
        Kleppmann DDIA (consistencia atomica via Lua), Anderson (least privilege),
        Prometheus Up & Running (labels baixa cardinalidade), Ramalho (tipos).

Invariante: 1 Lua EVAL atomico (ZREMRANGEBYSCORE + ZCARD + ZADD + EXPIRE).
Fallback: deque + RLock se Redis fora (degrada para in-memory por instancia).
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from typing import Final, Literal, TypedDict

logger = logging.getLogger(__name__)

_LUA_SCRIPT: Final[str] = (
    "local key=KEYS[1]; local now=ARGV[1]; local window=ARGV[2]; local max=ARGV[3]; local member=ARGV[4]; "
    "redis.call('ZREMRANGEBYSCORE',key,0,tonumber(now)-tonumber(window)); "
    "if redis.call('ZCARD',key) < tonumber(max) then "
    "redis.call('ZADD',key,tonumber(now),member); redis.call('PEXPIRE',key,math.ceil(tonumber(window)*1000)); return 1 else return 0 end"
)

class RateLimitConfig(TypedDict, total=False):
    max_tokens: int
    window_s: float
    prefix: str
    redis_url: str | None

Decision = Literal["allow", "deny"]
DEFAULT_MAX: Final[int] = 20
DEFAULT_WINDOW: Final[float] = 60.0
DEFAULT_PREFIX: Final[str] = "jefrey:ratelimit:"

_AUTO_REDIS = object()

class RateLimiter:
    """Rate-limiter distribuido (Redis Lua) com fallback local thread-safe."""

    def __init__(
        self,
        *,
        redis_client: object | None = _AUTO_REDIS,  # type: ignore[assignment]
        max_tokens: int = DEFAULT_MAX,
        window_s: float = DEFAULT_WINDOW,
        prefix: str = DEFAULT_PREFIX,
    ) -> None:
        self._max: int = int(max_tokens)
        self._window: float = float(window_s)
        self._prefix: str = prefix
        self._local: dict[str, deque[float]] = {}
        self._lock = threading.RLock()
        if redis_client is _AUTO_REDIS:
            # auto-resolve via settings
            self._redis: object | None = None
            try:
                from src.jefrey.core.config import get_settings
                url = get_settings().redis.dsn
                import redis as _redis  # type: ignore[import-not-found]
                cand = _redis.Redis.from_url(url, decode_responses=True)
                try:
                    cand.ping()  # type: ignore[union-attr]
                    self._redis = cand
                except Exception:
                    logger.warning("RateLimiter: Redis ping falhou, usando fallback local")
                    self._redis = None
            except Exception as e:
                logger.debug("RateLimiter: sem Redis (%s), fallback local", e)
                self._redis = None
        elif redis_client is None:
            self._redis = None
        else:
            self._redis = redis_client

    def _key(self, user_id: str, tool_name: str) -> str:
        safe_user = (user_id or "system").strip() or "system"
        safe_tool = (tool_name or "unknown").strip() or "unknown"
        return f"{self._prefix}{safe_user}:{safe_tool}"

    def is_allowed(self, user_id: str, tool_name: str) -> Decision:
        key = self._key(user_id, tool_name)
        now = time.time()
        max_v = self._max
        win = self._window
        decision: Decision = "allow"
        if self._redis is not None:
            try:
                member = f"{now}:{uuid.uuid4().hex[:8]}"
                res = self._redis.eval(_LUA_SCRIPT, 1, key, str(now), str(win), str(max_v), member)  # type: ignore[union-attr]
                decision = "allow" if int(res) == 1 else "deny"
                self._inc_metric(tool_name, decision)
                if decision == "deny":
                    self._inc_blocked(tool_name)
                return decision
            except Exception as e:
                logger.debug("RateLimiter Redis falhou (%s), fallback local", e)
        with self._lock:
            dq = self._local.get(key)
            if dq is None:
                dq = deque()
                self._local[key] = dq
            cutoff = now - win
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if len(dq) >= 10000:
                dq.popleft()
            if len(dq) < max_v:
                dq.append(now)
                decision = "allow"
            else:
                decision = "deny"
        self._inc_metric(tool_name, decision)
        if decision == "deny":
            self._inc_blocked(tool_name)
        return decision

    def _inc_metric(self, tool_name: str, decision: Decision) -> None:
        try:
            from src.jefrey.core.metrics import RATE_LIMIT_TOTAL
            RATE_LIMIT_TOTAL.labels(tool_name=tool_name, decision=decision).inc()
        except Exception:
            pass

    def _inc_blocked(self, tool_name: str) -> None:
        try:
            from src.jefrey.core.metrics import TOOLS_BLOCKED
            TOOLS_BLOCKED.labels(tool_name=tool_name, reason="rate_limit").inc()
        except Exception:
            pass

    def reset(self, user_id: str, tool_name: str) -> None:
        key = self._key(user_id, tool_name)
        with self._lock:
            self._local.pop(key, None)
        if self._redis is not None:
            try:
                self._redis.delete(key)  # type: ignore[union-attr]
            except Exception:
                pass

_rate_limiter: RateLimiter | None = None
_rate_lock = threading.Lock()

def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        with _rate_lock:
            if _rate_limiter is None:
                try:
                    from src.jefrey.core.config import get_settings
                    cfg = get_settings().policy
                    _rate_limiter = RateLimiter(
                        max_tokens=int(getattr(cfg, "rate_limit_max", DEFAULT_MAX)),
                        window_s=float(getattr(cfg, "rate_limit_window", DEFAULT_WINDOW)),
                    )
                except Exception:
                    _rate_limiter = RateLimiter()
    return _rate_limiter

def reset_rate_limiter() -> None:
    global _rate_limiter
    with _rate_lock:
        _rate_limiter = None
