"""Token introspection endpoint for OAuth2 (RFC 7662).

CIPHER-031: OAuth2 Token Validation — fail-closed, sem stub em prod
CIPHER-033: HMAC isolation (revogacao via hash, nunca token raw)
MCP Spec 2026-07-28: aud/iss/kid/alg obrigatorios
Axiom #6: fail-closed (prod sem AUD/ISS ou Redis -> RuntimeError)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time

logger = logging.getLogger(__name__)

_TOKEN_ACTIVE = "active"
_TOKEN_EXPIRED = "expired"
_TOKEN_REVOKED = "revoked"
_TOKEN_UNKNOWN = "unknown"

class IntrospectionResult:
    """Structured introspection result per RFC 7662."""
    def __init__(
        self,
        active: bool = False,
        token_type: str | None = None,
        scope: list[str] | None = None,
        client_id: str | None = None,
        sub: str | None = None,
        user_id: str | None = None,
        exp: int | None = None,
        iat: int | None = None,
        auth_time: int | None = None,
        revoked: bool | None = None,
        error: str | None = None,
    ):
        self.active = active
        self.token_type = token_type
        self.scope = scope or []
        self.client_id = client_id
        self.sub = sub
        self.user_id = user_id
        self.exp = exp
        self.iat = iat
        self.auth_time = auth_time
        self.revoked = revoked
        self.error = error

    def to_dict(self) -> dict:
        result: dict = {"active": self.active}
        if self.token_type: result["token_type"] = self.token_type
        if self.scope: result["scope"] = " ".join(self.scope) if len(self.scope)==1 else self.scope
        if self.client_id: result["client_id"] = self.client_id
        if self.sub: result["sub"] = self.sub
        if self.user_id: result["user_id"] = self.user_id
        if self.exp: result["exp"] = self.exp
        if self.iat: result["iat"] = self.iat
        if self.auth_time: result["auth_time"] = self.auth_time
        if self.revoked is not None: result["revoked"] = self.revoked
        if self.error: result["error"] = self.error
        return result

# Fallback in-memory apenas dev (prod usa Redis) — nunca com token raw, sempre hash
_active_tokens: dict[str, IntrospectionResult] = {}

def _is_prod() -> bool:
    return os.getenv("JEFREY_ENV", "dev") == "prod"

def _get_redis():
    """Lazy Redis — fail-closed em prod (CIPHER-031)."""
    import redis as redis_lib
    url = os.getenv("JEFREY_REDIS__URL", "")
    host = os.getenv("JEFREY_REDIS__HOST", "")
    pwd = os.getenv("JEFREY_REDIS__PASSWORD", "")
    # prefer URL
    if url and "://" in url:
        return redis_lib.from_url(url, decode_responses=True, socket_connect_timeout=2)
    if host:
        return redis_lib.Redis(host=host, port=int(os.getenv("JEFREY_REDIS__PORT","6379")), password=pwd or None, decode_responses=True, socket_connect_timeout=2)
    if url:
        return redis_lib.from_url(url, decode_responses=True, socket_connect_timeout=2)
    # fallback localhost (dev only)
    if _is_prod():
        raise RuntimeError("JEFREY_REDIS__URL/HOST ausente em prod (A2 fail-closed)")
    return redis_lib.Redis(host="localhost", port=6379, decode_responses=True, socket_connect_timeout=2)

def _is_revoked_hash(token_hash: str) -> bool:
    """Checa revogacao no Redis (prod) ou dict (dev fallback). Fail-closed em prod."""
    try:
        r = _get_redis()
        return bool(r.sismember("jefrey:revoked_tokens", token_hash))
    except Exception as e:
        if _is_prod():
            raise RuntimeError(f"Redis revocation check falhou em prod (fail-closed): {e}") from e
        logger.warning("Redis revocation check falhou em dev (fallback dict): %s", e)
        v = _active_tokens.get(token_hash)
        return bool(v and v.revoked)

def _store_revoked_hash(token_hash: str, ttl_seconds: int = 86400) -> None:
    """Armazena hash revogado com TTL (24h default ou ate exp). Evita vazamento infinito (DDIA)."""
    try:
        r = _get_redis()
        r.sadd("jefrey:revoked_tokens", token_hash)
        # TTL para nao vazar para sempre — expira com o token (DDIA). Se token expirou, revoked desnecessario.
        try:
            # Se ja tem TTL, mantem; senao define 24h
            if r.ttl("jefrey:revoked_tokens") == -1:
                r.expire("jefrey:revoked_tokens", ttl_seconds)
        except Exception as _e:
            logger.debug("revoked TTL compat: %s", _e)
    except Exception as e:
        if _is_prod():
            raise RuntimeError(f"Redis revoke falhou em prod (fail-closed): {e}") from e
        logger.warning("Redis revoke falhou em dev (fallback dict): %s", e)
        _active_tokens[token_hash] = IntrospectionResult(active=False, revoked=True, error="revoked")

def introspect_token(token: str, client_id: str | None = None) -> IntrospectionResult:
    """RFC 7662 — valida via jwt.decode(RS256,kid,aud,iss,exp). Fail-closed em prod."""
    if not token or token.strip() == "":
        return IntrospectionResult(active=False, error="invalid_token")

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    # 1) stub valid_ — APENAS dev (SEM STUB EM PROD — CIPHER-021) — antes de Redis para nao exigir Redis em prod para stub
    if token.startswith("valid_"):
        if _is_prod():
            return IntrospectionResult(active=False, error="invalid_token")
        logger.warning("valid_ stub aceito apenas em dev (A2) — hash=%s...", token_hash[:12])
        now = int(time.time())
        result = IntrospectionResult(active=True, token_type="Bearer", scope=["openid"], client_id=client_id or "dev-client", sub="dev-user", user_id="dev-user", exp=now+3600, iat=now)
        _active_tokens[token_hash] = result
        return result

    # 2) revogacao (hash, nunca token raw — Security Eng ch.5) — apenas para tokens reais
    try:
        if _is_revoked_hash(token_hash):
            return IntrospectionResult(active=False, revoked=True)
    except RuntimeError:
        raise
    except Exception as e:
        logger.warning("revocation check error: %s", e)
        if _is_prod():
            raise RuntimeError(f"revocation check falhou: {e}") from e

    # 3) JWT real — kid/alg/aud/iss/exp obrigatorios (MCP Spec 2026-07-28)
    try:
        import jwt
    except ImportError as e:
        raise RuntimeError("PyJWT ausente (pip install PyJWT)") from e

    parts = token.split(".")
    if len(parts) != 3:
        return IntrospectionResult(active=False, error="invalid_token")

    # header sem verificar para extrair kid/alg (fail-closed se ausentes)
    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        return IntrospectionResult(active=False, error="invalid_token")

    alg = header.get("alg")
    kid = header.get("kid")
    if alg != "RS256":
        return IntrospectionResult(active=False, error="invalid_alg")
    if not kid:
        return IntrospectionResult(active=False, error="missing_kid")

    # aud/iss obrigatorios — fail-closed em prod se ausentes no env
    aud = os.getenv("JEFREY_OAUTH__AUD", "")
    iss = os.getenv("JEFREY_OAUTH__ISS", "")
    if not aud or not iss:
        if _is_prod():
            raise RuntimeError("JEFREY_OAUTH__AUD/ISS ausentes em prod (A6 fail-closed)")
        aud = aud or "jefrey"
        iss = iss or "https://auth.jefrey.ai"
        logger.warning("AUD/ISS fallback dev: aud=%s iss=%s", aud, iss)

    # resolver chave publica via JWKS por kid (A1 urlsafe ja correto)
    from src.jefrey.oauth2.jwks import get_jwks
    jwks = get_jwks()
    jwk = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if not jwk:
        return IntrospectionResult(active=False, error="unknown_kid")
    try:
        from jwt.algorithms import RSAAlgorithm
        public_key = RSAAlgorithm.from_jwk(json.dumps(jwk))
    except Exception as e:
        logger.warning("JWK->public_key falhou kid=%s: %s", kid, e)
        return IntrospectionResult(active=False, error="invalid_kid")

    try:
        payload = jwt.decode(token, public_key, algorithms=["RS256"], audience=aud, issuer=iss, options={"require": ["exp","iat","aud","iss"]})
    except jwt.ExpiredSignatureError:
        return IntrospectionResult(active=False, error="token_expired")
    except jwt.InvalidAudienceError:
        return IntrospectionResult(active=False, error="invalid_audience")
    except jwt.InvalidIssuerError:
        return IntrospectionResult(active=False, error="invalid_issuer")
    except jwt.InvalidTokenError as e:
        logger.warning("jwt.decode falhou: %s", e)
        return IntrospectionResult(active=False, error="invalid_token")

    # build result
    scopes = payload.get("scope", "")
    if isinstance(scopes, str):
        scope_list = [s.strip() for s in scopes.split(" ") if s.strip()]
    elif isinstance(scopes, list):
        scope_list = scopes
    else:
        scope_list = []

    token_client_id = payload.get("client_id")
    if client_id and token_client_id != client_id:
        logger.warning("client_id mismatch token=%s expected=%s", token_client_id, client_id)

    token_user_id = payload.get("sub") or payload.get("user_id")
    if not token_user_id:
        return IntrospectionResult(active=False, error="missing_sub")

    exp = payload.get("exp"); iat = payload.get("iat")
    return IntrospectionResult(active=True, token_type="Bearer", scope=scope_list, client_id=token_client_id, sub=payload.get("sub"), user_id=token_user_id, exp=exp, iat=iat, auth_time=payload.get("auth_time"))

def revoke_token(token: str) -> bool:
    if not token:
        return False
    h = hashlib.sha256(token.encode("utf-8")).hexdigest()
    # TTL = max(TTL ate exp, 1h minimo) para limpar revoked apos token expirar
    try:
        _store_revoked_hash(h, ttl_seconds=86400)
    except TypeError:
        _store_revoked_hash(h)
    logger.info("Token revoked hash=%s...", h[:16])
    return True

def clear_revoked_tokens() -> int:
    """Remove revogados do Redis (ou dict dev)."""
    try:
        r = _get_redis()
        # scan revoked set — nao ha como saber quais sao revogados sem set; apenas count
        members = r.smembers("jefrey:revoked_tokens")
        if members:
            r.delete("jefrey:revoked_tokens")
        dev_c = sum(1 for v in _active_tokens.values() if v.revoked)
        _active_tokens.clear()
        return len(members) if members else dev_c
    except Exception as e:
        if _is_prod():
            raise RuntimeError(f"clear_revoked_tokens falhou em prod: {e}") from e
        c = sum(1 for v in _active_tokens.values() if v.revoked)
        _active_tokens.clear()
        return c
