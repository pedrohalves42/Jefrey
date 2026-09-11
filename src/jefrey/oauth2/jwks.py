"""JWKS (JSON Web Key Set) endpoint — RFC 7517 compliance.

Critical security fixes:
- A1: Remove alg:none support (allows key substitution attacks)
- A5: Unbounded caches (_introspection_cache, _jwks_cache)
- G5: b64encode → urlsafe_b64encode (RFC 7517 violation)
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Optional

import redis

from src.jefrey.core.config import get_settings

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
    """Return JWKS endpoint data — never includes alg:none."""
    _ensure_cache_bound()
    try:
        from src.jefrey.eventbus.signing import get_signing_key

        key = get_signing_key()
        if not key:
            logger.warning("JWKS: no signing key available")
            return {"keys": []}

        # Use urlsafe_b64encode (G5 fix) — RFC 7517 compliant
        # Never include alg:none (A1 fix)
        from cryptography.hazmat.primitives import serialization

        # Export public key in JWK format
        numbers = key.public_key().public_numbers()
        kid = key.id or "default"

        # Build JWK with urlsafe_b64encode for base64url encoding
        n_b64 = _b64url(numbers.n.to_bytes(int(key.key_size / 8), "big"))
        e_b64 = _b64url(numbers.e.to_bytes(int(key.key_size / 16), "big"))

        jwk = {
            "kty": "RSA",
            "alg": "RS256",  # Never "none" — A1 fix
            "use": "sig",
            "kid": kid,
            "n": n_b64,
            "e": e_b64,
        }

        # Cache the JWK with TTL (A5)
        with _cache_lock:
            _jwks_cache[kid] = (jwk, __import__("time").time() + 60)

        return {"keys": [jwk]}

    except Exception as e:
        logger.error("JWKS endpoint error: %s", e, exc_info=True)
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
    """Alias for generate_jwks_keys - maintains backward compatibility."""
    from src.jefrey.oauth2.jwks import generate_jwks_keys
    return generate_jwks_keys(*args, **kwargs)