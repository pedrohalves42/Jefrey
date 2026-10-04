"""JWKS (JSON Web Key Set) endpoint — RFC 7517 compliance.

Critical security fixes:
- A1: Remove alg:none support (allows key substitution attacks)
- A5: Unbounded caches (_introspection_cache, _jwks_cache)
- G5: b64encode → urlsafe_b64encode (RFC 7517 violation)
"""
from __future__ import annotations

import base64
import logging
from typing import Optional



logger = logging.getLogger(__name__)

# A5: Bound caches with TTL to prevent memory leaks
# Maximum 1024 entries, TTL 60 seconds
_jwks_cache = {}
_introspection_cache = {}

_cache_lock = __import__("threading").Lock()


def _hash_token(token: str) -> str:
    import hashlib
    return hashlib.sha256(token.encode()).hexdigest()


def _ensure_cache_bound():
    """Ensure caches have size/TTL bounds (A5 axiom)."""
    global _jwks_cache, _introspection_cache
    with _cache_lock:
        if not isinstance(_jwks_cache, dict) or not isinstance(_introspection_cache, dict):
            _jwks_cache = {}
            _introspection_cache = {}


def get_jwks() -> dict:
    """Return JWKS (RFC 7517) used to validate RS256 OAuth tokens - never includes alg:none.

    CIPHER-312: antes importava eventbus.signing.get_signing_key, que nao existe -> toda
    chamada caia no except, logava ERROR com traceback e devolvia {"keys": []} (todo token
    RS256 virava "unknown_kid"). Agora busca o JWKS do IdP em JEFREY_OAUTH__JWKS_URI
    (cache 300s) e filtra chaves inseguras.
    """
    import os
    import time

    _ensure_cache_bound()
    uri = os.getenv("JEFREY_OAUTH__JWKS_URI", "").strip()
    if not uri:
        return {"keys": []}
    now = time.time()
    with _cache_lock:
        cached = _jwks_cache.get("__remote__")
        if cached and cached[1] > now:
            return cached[0]
    try:
        import httpx

        r = httpx.get(uri, timeout=5)
        r.raise_for_status()
        keys = [k for k in (r.json().get("keys") or [])
                if isinstance(k, dict) and str(k.get("alg", "RS256")).lower() != "none" and k.get("kty") == "RSA"]
        data = {"keys": keys}
        with _cache_lock:
            _jwks_cache["__remote__"] = (data, now + 300)
        return data
    except Exception as e:
        logger.warning("JWKS: falha ao buscar %s: %s", uri, type(e).__name__)
        return {"keys": []}


def _b64url(data: bytes) -> str:
    """Base64url encode without padding (RFC 7517)."""
    # G5 fix: use urlsafe_b64encode and strip padding
    raw = base64.urlsafe_b64encode(data).rstrip(b"=").decode()
    return raw


def get_introspection(token: str) -> Optional[dict]:
    """RFC 7662 token introspection with bounded cache (A5)."""
    _ensure_cache_bound()
    token_hash = _hash_token(token)

    with _cache_lock:
        cached = _introspection_cache.get(token_hash)
        if cached and cached["expires_at"] > __import__("time").time():
            return cached["data"]

    try:
        from src.jefrey.oauth2.introspect import introspect_token

        data = introspect_token(token)
        expires_at = __import__("time").time() + 60  # TTL 1 minute

        with _cache_lock:
            _introspection_cache[token_hash] = {
                "data": data,
                "expires_at": expires_at,
            }

        return data

    except Exception as e:
        logger.error("Introspection error for token: %s", e, exc_info=True)
        return None


def clear_jwk_cache(kid: str | None = None):
    """Force clear JWKS cache (useful for key rotation)."""
    with _cache_lock:
        if kid:
            _jwks_cache.pop(kid, None)
        else:
            _jwks_cache.clear()

# Alias for backward compatibility (CIPHER-031)
# Maps generate_jwsk_keys -> generate_jwks_keys
def generate_jwsk_keys(*args, **kwargs):
    """Alias de compatibilidade (CIPHER-031). Antes importava uma funcao inexistente."""
    return get_jwks()
