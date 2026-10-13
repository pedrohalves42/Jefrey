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
from pathlib import Path
import logging
import os

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse

from src.jefrey.core.config import get_settings
from src.jefrey.oauth2.introspect import introspect_token, IntrospectionResult

logger = logging.getLogger(__name__)

_PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/metrics", "/", "/vite.svg", "/favicon.ico", "/api/status", "/auth/dev-token", "/channels/whatsapp/webhook", "/auth/google/login", "/auth/google/callback", "/settings/llm/openrouter/callback", "/connections/google/callback", "/manifest.json", "/sw.js", "/stt/health", "/tts/health", "/stt/status", "/tts/status", "/auth/stt/health", "/auth/tts/health", "/auth/stt/status", "/auth/tts/status"}
# UI-1 Shell public — Axiom 5 least privilege (Livro 3 Security Eng cap8, CIPHER-019)
# /chat|/memory|/approvals continuam protegidos; /assets/* sao build Vite hashados sem user data
# /auth/dev-token e publico mas fail-closed em prod (CIPHER-021, auth.py is_prod 403)
_PUBLIC_PREFIXES = ("/assets/", "/images/", "/wa/device/")  # /images: icones do manifesto; /wa/device/: a extensao do Chrome (token proprio do aparelho)

# Paginas do app (React Router). Sao tambem prefixos de API (/memory, /approvals...), entao so
# servimos o index.html quando e navegacao de navegador (GET + Accept: text/html).
_SPA_PAGES = {"/studio", "/memory", "/approvals", "/observability", "/settings", "/knowledge", "/chat",
              "/memoria", "/skills", "/configuracoes", "/avancado", "/bem-vindo", "/primeira-vez", "/hoje", "/conexoes", "/ajuda", "/aprendi", "/estudos", "/termos", "/privacidade", "/aprender", "/orb"}
_INDEX_HTML = Path(__file__).resolve().parent.parent / "static" / "index.html"
# CIPHER-301: /chat aceita modo anonimo, mas se vier Authorization a identidade e validada
# (antes /chat e /chat/status eram publicos e todos viravam "anonymous": um usuario lia a
# resposta do outro). /hmac-status e /rotate-hmac sairam da lista publica (vazavam a chave HMAC).
def _anonymous_chat_allowed() -> bool:
    """Chat anonimo vem DESLIGADO: sem token -> 401. Opt-in so para demonstracao."""
    return os.getenv("JEFREY_API__ALLOW_ANONYMOUS_CHAT", "").strip().lower() in ("1", "true", "yes")


_OPTIONAL_AUTH_PATHS = {"/chat", "/chat/stream"}
_OPTIONAL_AUTH_PREFIXES = ("/chat/status/",)

# CIPHER-302: dev-token agora e um JWT HS256 assinado com JEFREY_API__SECRET_KEY (sub = user_id).
# A secret_key em si continua aceita como "token de servico" (n8n/CLI) e so nesse caso
# o header X-User-Id e respeitado.
_DEV_JWT_ISS = "jefrey-dev"


def _decode_dev_jwt(token: str, secret: str) -> str | None:
    """Retorna o user_id (sub) de um dev-token valido, ou None."""
    if token.count(".") != 2:
        return None
    try:
        import jwt  # PyJWT
        claims = jwt.decode(token, secret, algorithms=["HS256"], issuer=_DEV_JWT_ISS,
                            options={"require": ["exp", "sub", "iss"]})
        sub = str(claims.get("sub") or "").strip()
        return sub or None
    except Exception as e:  # expirado, assinatura invalida, etc.
        logger.warning("dev-token JWT invalido: %s", type(e).__name__)
        return None


# CIPHER-307: rate limit HTTP por identidade (antes 70 req seguidas = 70x 200).
_RL_LIMIT_PER_MIN = 60
_RL_BURST = 20
_RL_NATIVE_PER_MIN = 600
_RL_NATIVE_BURST = 120
_RL_EXEMPT_PREFIXES = ("/assets/", "/health", "/metrics", "/api/status", "/stt/health", "/tts/health", "/wa/device/",
                       "/stt/status", "/tts/status", "/favicon.ico", "/manifest.json", "/sw.js", "/vite.svg")
def _native_mode() -> bool:
    return (os.getenv("JEFREY_MODE", "") or "").strip().lower() == "native"


_USER_RL_EXEMPT = ("/system/wake", "/system/activity", "/system/telemetry", "/wa/pending")  # so leitura, baratas, perguntadas de poucos em poucos segundos
_rl_buckets: dict[str, tuple[float, float]] = {}


def _rl_allow(key: str) -> tuple[bool, int]:
    """Token bucket em memoria: 60/min sustentado + burst 20. Retorna (permitido, retry_after_s)."""
    import os as _os
    # programa nativo = uma pessoa so, em 127.0.0.1: abrir uma tela dispara ~20 pedidos de uma vez, entao o limite e folgado
    # (continua protegendo contra laco descontrolado); no servidor continua 60/min
    per_min, burst = (_RL_NATIVE_PER_MIN, _RL_NATIVE_BURST) if _native_mode() else (_RL_LIMIT_PER_MIN, _RL_BURST)
    try:
        rate = float(_os.getenv("JEFREY_HTTP_RATE_PER_MIN", per_min)) / 60.0
        cap = float(_os.getenv("JEFREY_HTTP_RATE_BURST", burst))
    except ValueError:
        rate, cap = per_min / 60.0, float(burst)
    now = time.monotonic()
    tokens, last = _rl_buckets.get(key, (cap, now))
    tokens = min(cap, tokens + (now - last) * rate)
    if tokens < 1.0:
        _rl_buckets[key] = (tokens, now)
        return False, max(1, int((1.0 - tokens) / rate) + 1)
    _rl_buckets[key] = (tokens - 1.0, now)
    if len(_rl_buckets) > 10000:  # evita crescimento ilimitado
        _rl_buckets.clear()
    return True, 0

# A5: cache com TTL 60s, max 1024, chave = hash(token) nunca token raw
_CACHE_TTL = 60
_CACHE_MAXSIZE = 1024
try:
    from cachetools import TTLCache as _TTLCache
    _introspection_cache = _TTLCache(maxsize=_CACHE_MAXSIZE, ttl=_CACHE_TTL)
    _USE_TTLCACHE = True
except ImportError:
    _introspection_cache: dict[str, tuple[IntrospectionResult, float]] = {}  # type: ignore
    _USE_TTLCACHE = False

def _cache_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def _cache_get(token: str) -> IntrospectionResult | None:
    k = _cache_key(token)
    if _USE_TTLCACHE:
        item = _introspection_cache.get(k)  # type: ignore
        if item is None:
            return None
        # TTLCache already expires automatically, but return the result part for consistency
        return item[0] if isinstance(item, tuple) else item
    else:
        item = _introspection_cache.get(k)  # type: ignore
        if item is None:
            return None
        result, exp = item
        if time.time() > exp:
            _introspection_cache.pop(k, None)  # type: ignore
            return None
        return result

def _cache_set(token: str, result: IntrospectionResult) -> None:
    k = _cache_key(token)
    if _USE_TTLCACHE:
        _introspection_cache[k] = result  # type: ignore
    else:
        # evict oldest if over maxsize (simple FIFO)
        if len(_introspection_cache) >= _CACHE_MAXSIZE:  # type: ignore
            oldest = next(iter(_introspection_cache))  # type: ignore
            _introspection_cache.pop(oldest, None)  # type: ignore
        _introspection_cache[k] = (result, time.time() + _CACHE_TTL)  # type: ignore

class FastAPIAuthMiddleware(BaseHTTPMiddleware):
    """CIPHER-019 extensao: valida Bearer token em endpoints FastAPI."""

    async def dispatch(self, request: Request, call_next):
        # CORS preflight: never block OPTIONS - let CORSMiddleware handle headers
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.url.path
        if (request.method == "GET" and path.rstrip("/") in _SPA_PAGES
                and "text/html" in request.headers.get("accept", "") and _INDEX_HTML.exists()):
            return FileResponse(_INDEX_HTML)
        # UI-1 public whitelist — FAIL-CLOSED exceto UI estatica (Axiom 5, CIPHER-019)
        # no modo nativo as metricas (contagens de uso, nomes de modelos e ferramentas) pedem login como o resto
        if (path in _PUBLIC_PATHS or path.startswith(_PUBLIC_PREFIXES)) and not (path == "/metrics" and _native_mode()):
            request.state.user_id = "system"
            if not path.startswith(_RL_EXEMPT_PREFIXES) and path not in ("/", "/docs", "/redoc", "/openapi.json"):
                ip = request.client.host if request.client else "unknown"
                ok, retry = _rl_allow(f"ip:{ip}:{path}")
                if not ok:
                    return JSONResponse({"ok": False, "error": "muitas requisicoes"}, status_code=429, headers={"Retry-After": str(retry)})
            return await call_next(request)

        auth = request.headers.get("Authorization", "")

        optional = _anonymous_chat_allowed() and (path in _OPTIONAL_AUTH_PATHS or path.startswith(_OPTIONAL_AUTH_PREFIXES))
        if not auth and optional:
            request.state.user_id = "anonymous"
            ip = request.client.host if request.client else "unknown"
            ok, retry = _rl_allow(f"ip:{ip}")
            if not ok:
                return JSONResponse({"ok": False, "error": "muitas requisicoes"}, status_code=429, headers={"Retry-After": str(retry)})
            return await call_next(request)

        if not auth:
            logger.warning("FastAPI: Authorization header missing (path=%s)", path)
            return JSONResponse({"ok": False, "error": "token nao fornecido"}, status_code=401)

        parts = auth.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return JSONResponse({"ok": False, "error": "formato de token invalido use Bearer <token>"}, status_code=401)

        token = parts[1]
        secret = get_settings().api.secret_key

        if secret:
            identity = None
            client = None
            expected = f"Bearer {secret}"
            if hmac.compare_digest(auth, expected):
                # token de servico (n8n/CLI/scripts): age em nome de X-User-Id
                identity = request.headers.get("X-User-Id") or "service"
                client = "configured-secret"
            else:
                identity = _decode_dev_jwt(token, secret)
                client = "dev-token" if identity else None
            if identity:
                # consultas leves de segundo plano (a tela pergunta sempre) nao gastam o limite da pessoa
                ok, retry = (True, 0) if path in _USER_RL_EXEMPT else _rl_allow(f"user:{identity}")
                if not ok:
                    return JSONResponse({"ok": False, "error": "muitas requisicoes"}, status_code=429, headers={"Retry-After": str(retry)})
                request.state.user_id = identity
                request.state.oauth2_client = client
                return await call_next(request)

        # A5: check cache por hash (nunca token raw) — CIPHER-121 revocation check antes do cache
        try:
            cached = _cache_get(token)
            if cached is not None:
                # CIPHER-121: invalida cache se token foi revogado apos cacheamento (janela 60s)
                try:
                    from src.jefrey.oauth2.introspect import _is_revoked_hash
                    if _is_revoked_hash(_cache_key(token)):
                        _introspection_cache.pop(_cache_key(token), None)  # type: ignore
                        cached = None
                except Exception as _e:
                    logger.debug("ignorado (%s): %s", 'auth_middleware.py', type(_e).__name__)
                if cached is not None:
                    result = cached
                else:
                    result = introspect_token(token=token)
                    _cache_set(token, result)
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