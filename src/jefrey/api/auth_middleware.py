"""Middleware de autenticacao para FastAPI (SECURITY P6-pre).

Adiciona:
- Bearer token validation (CIPHER-019 estendido para FastAPI) com comparacao timing-safe
- User context extraction (X-User-Id header)
- OAuth2 token introspection via CIPHER-031 (JWKS + Redis validation)
- Per-tenant client_id isolation
- A5: TTLCache 1024/60 + hash(token) nunca token raw (DDIA ch.5, Security Eng ch.5)
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.jefrey.core.config import get_settings
from src.jefrey.oauth2.introspect import introspect_token, IntrospectionResult

logger = logging.getLogger(__name__)

_PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/metrics"}

# A5: cache com TTL 60s, max 1024, chave = hash(token) nunca token raw
_CACHE_TTL = 60
_CACHE_MAXSIZE = 1024
try:
    from cachetools import TTLCache as _TTLCache
    _introspection_cache = _TTLCache(maxsize=_CACHE_MAXSIZE, ttl=_CACHE_TTL)
    _USE_TTLCACHE = True
except ImportError:
    _introspection_cache: dict[str, tuple[IntrospectionResult, float]] = {}
    _USE_TTLCACHE = False

def _cache_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def _cache_get(token: str) -> IntrospectionResult | None:
    k = _cache_key(token)
    if _USE_TTLCACHE:
        return _introspection_cache.get(k)  # type: ignore
    else:
        item = _introspection_cache.get(k)
        if item is None:
            return None
        result, exp = item
        if time.time() > exp:
            _introspection_cache.pop(k, None)
            return None
        return result

def _cache_set(token: str, result: IntrospectionResult) -> None:
    k = _cache_key(token)
    if _USE_TTLCACHE:
        _introspection_cache[k] = result  # type: ignore
    else:
        # evict oldest if over maxsize (simple FIFO)
        if len(_introspection_cache) >= _CACHE_MAXSIZE:
            oldest = next(iter(_introspection_cache))
            _introspection_cache.pop(oldest, None)
        _introspection_cache[k] = (result, time.time() + _CACHE_TTL)

class FastAPIAuthMiddleware(BaseHTTPMiddleware):
    """CIPHER-019 extensao: valida Bearer token em endpoints FastAPI."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _PUBLIC_PATHS:
            request.state.user_id = "system"
            return await call_next(request)

        auth = request.headers.get("Authorization", "")

        if not auth:
            logger.warning("FastAPI: Authorization header missing (path=%s)", path)
            return JSONResponse({"ok": False, "error": "token nao fornecido"}, status_code=401)

        parts = auth.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return JSONResponse({"ok": False, "error": "formato de token invalido use Bearer <token>"}, status_code=401)

        token = parts[1]
        secret = get_settings().api.secret_key

        if secret:
            expected = f"Bearer {secret}"
            if hmac.compare_digest(auth, expected):
                request.state.user_id = request.headers.get("X-User-Id", "anonymous")
                request.state.oauth2_client = "configured-secret"
                return await call_next(request)

        # A5: check cache por hash (nunca token raw)
        try:
            cached = _cache_get(token)
            if cached is not None:
                result = cached
            else:
                result = introspect_token(token=token)
                # cache only successful active tokens or definitive inactive (not exceptions)
                _cache_set(token, result)

            if not result.active:
                logger.warning("OAuth2 introspection: token inactive (error=%s hash=%s...)", result.error, _cache_key(token)[:12])
                return JSONResponse({"ok": False, "error": "token inativo ou invalido"}, status_code=401)

            if not result.user_id:
                logger.warning("OAuth2 token missing user_id (hash=%s...)", _cache_key(token)[:12])
                return JSONResponse({"ok": False, "error": "token nao possui identificador de usuario"}, status_code=401)

            request.state.user_id = result.user_id
            request.state.oauth2_client = result.client_id or "unknown"
            request.state.oauth2_scopes = result.scope or []
            request.state.oauth2_token_exp = result.exp

            logger.info("OAuth2 OK user_id=%s client_id=%s scopes=%s", result.user_id, result.client_id, " ".join(result.scope) if result.scope else "none")
            return await call_next(request)

        except RuntimeError as e:
            # fail-closed em prod (A2/A5)
            logger.error("OAuth2 fail-closed: %s", e, exc_info=True)
            return JSONResponse({"ok": False, "error": "erro interno de validacao de token"}, status_code=503)
        except Exception as e:
            logger.error("OAuth2 introspection error: %s", e, exc_info=True)
            return JSONResponse({"ok": False, "error": "erro interno de validacao de token"}, status_code=503)

        logger.warning("FastAPI: OAuth2 validation failed (path=%s hash=%s...)", path, _cache_key(token)[:12])
        return JSONResponse({"ok": False, "error": "nao autorizado"}, status_code=401)
