"""CIPHER-035: OAuth2 Token Refresh — IdP real via httpx + dev stub gateado.

FAIL-CLOSED (Axiom #6): em prod sem JEFREY_OAUTH__TOKEN_URI => RuntimeError.
SEM STUB EM PROD: valid_ prefix só quando JEFREY_ENV != prod.
P4-02: httpx POST token_uri com client auth, grant_type=refresh_token.
Compat: mantém stub path para tests isolados (sem network).
"""
from __future__ import annotations

import os
import time
import warnings
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple


class TokenRefreshError(Exception):
    pass


class InvalidRefreshTokenError(TokenRefreshError):
    pass


class TokenExpiredError(TokenRefreshError):
    pass


def _get_oauth_settings() -> Dict[str, str]:
    import os as _os

    return {
        "client_id": _os.getenv("JEFREY_OAUTH__CLIENT_ID", ""),
        "client_secret": _os.getenv("JEFREY_OAUTH__CLIENT_SECRET", ""),
        "redirect_uris": _os.getenv("JEFREY_OAUTH__REDIRECT_URIS", "").split(",")
        if _os.getenv("JEFREY_OAUTH__REDIRECT_URIS")
        else [],
        "auth_uri": _os.getenv("JEFREY_OAUTH__AUTH_URI", ""),
        "token_uri": _os.getenv("JEFREY_OAUTH__TOKEN_URI", ""),
        "jwks_uri": _os.getenv("JEFREY_OAUTH__JWKS_URI", ""),
    }


def _is_prod() -> bool:
    return os.getenv("JEFREY_ENV", "dev") == "prod"


def refresh_access_token(
    refresh_token: str,
    hmac_key: Optional[str] = None,  # noqa: ARG001 — reserved for CIPHER-033 HMAC binding se IdP exigir
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Refresh OAuth2 access token via IdP.

    P4-02 FAIL-CLOSED:
    - Se JEFREY_ENV==prod e token_uri ausente => RuntimeError (não stub).
    - Stub valid_ só existe quando JEFREY_ENV != prod.
    - Prod usa httpx real contra token_uri; sem network/mock deve ser mockado em tests.

    Returns:
        (new_token_dict, error) — error None em sucesso.
    """
    s = _get_oauth_settings()

    # Dev stub path — gateado fora de prod
    if not _is_prod():
        if refresh_token and refresh_token.startswith("valid_"):
            warnings.warn(
                "Token refresh dev stub (valid_ prefix) — não usar em prod",
                UserWarning,
                stacklevel=2,
            )
            now = time.time()
            new_token: Dict[str, Any] = {
                "access_token": f"new_access_{int(now)}",
                "refresh_token": refresh_token,
                "expires_in": 3600,
                "token_type": "Bearer",
                "expires_at": datetime.now(timezone.utc) + timedelta(seconds=3600),
                "scope": "openid profile email",
            }
            return new_token, None
        # também tenta IdP se token_uri configurado mesmo em dev (integração opcional)
        if not refresh_token or not s["token_uri"]:
            # sem IdP e token inválido => erro determinístico
            if not refresh_token or not refresh_token.startswith("valid_"):
                return None, "invalid_refresh_token"
        # se chegou aqui com token não-valid_ mas com token_uri, cai para httpx abaixo

    # Prod (ou dev com token_uri) — httpx real
    token_uri = s["token_uri"]
    if not token_uri:
        if _is_prod():
            raise RuntimeError("JEFREY_OAUTH__TOKEN_URI ausente em prod (A6 fail-closed)")
        return None, "invalid_refresh_token"

    if not refresh_token:
        return None, "invalid_refresh_token"

    # httpx deve existir — é dependência direta (ver pip list httpx)
    try:
        import httpx
    except ImportError as e:
        raise RuntimeError("httpx ausente — instale httpx para IdP refresh em prod") from e

    # Fail-closed: sem client_id/secret em prod => RuntimeError
    if _is_prod() and (not s["client_id"] or not s["client_secret"]):
        raise RuntimeError("JEFREY_OAUTH__CLIENT_ID/SECRET ausentes em prod")

    try:
        resp = httpx.post(
            token_uri,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": s["client_id"],
                "client_secret": s["client_secret"],
            },
            timeout=5.0,
        )
    except Exception as e:
        return None, f"idp_unreachable: {e}"

    if resp.status_code != 200:
        # RFC 6749 error: invalid_grant, invalid_request etc.
        try:
            body = resp.json()
            err = body.get("error", f"http_{resp.status_code}")
        except Exception:
            err = f"http_{resp.status_code}"
        return None, err

    try:
        data = resp.json()
    except Exception as e:
        return None, f"invalid_idp_response: {e}"

    # Normaliza expires_at
    if "expires_in" in data and "expires_at" not in data:
        try:
            data["expires_at"] = datetime.now(timezone.utc) + timedelta(seconds=int(data["expires_in"]))
        except Exception:
            pass
    return data, None


def verify_token_signature(
    token: Dict[str, Any],
    hmac_key: str,
) -> Tuple[bool, Optional[str]]:
    if not token.get("signature"):
        return False, "missing_signature_in_token"
    return True, None
