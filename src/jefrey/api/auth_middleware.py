"""Middleware de autenticacao para FastAPI (SECURITY P6-pre).

Adiciona:
- Bearer token validation (CIPHER-019 estendido para FastAPI) com comparacao timing-safe
- User context extraction (X-User-Id header)
"""
from __future__ import annotations

import hmac
import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.jefrey.core.config import get_settings

logger = logging.getLogger(__name__)

# Endpoints que NAO exigem autenticacao (health check, docs)
_PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/metrics"}

class FastAPIAuthMiddleware(BaseHTTPMiddleware):
    """CIPHER-019 extensao: valida Bearer token em endpoints FastAPI.

    Extrai user_id do header X-User-Id para isolamento multi-tenant.
    Endpoints em _PUBLIC_PATHS nao exigem autenticacao.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Endpoints publicos (health, docs, metrics) -- sem auth
        if path in _PUBLIC_PATHS:
            request.state.user_id = "system"
            return await call_next(request)

        # Validacao Bearer token
        secret = get_settings().api.secret_key
        auth = request.headers.get("Authorization", "")

        if not secret:
            # SECURITY: secret vazio = sem auth possivel = recusa total
            logger.warning("FastAPI: secret_key vazio -- recusando request (path=%s)", path)
            return JSONResponse(
                {"ok": False, "error": "servidor nao configurado para autenticacao"},
                status_code=503,
            )

        # SECURITY (CIPHER-003): comparacao timing-safe para evitar timing attack
        expected = f"Bearer {secret}"
        if not hmac.compare_digest(auth, expected):
            return JSONResponse(
                {"ok": False, "error": "nao autorizado"},
                status_code=401,
            )

        # Extrai user_id para isolamento multi-tenant
        request.state.user_id = request.headers.get("X-User-Id", "anonymous")
        return await call_next(request)
