"""
CIPHER-033: EventBus Message Signing — HMAC-SHA256 per-tenant (Axiom #2, #6)

Fail-closed (Security Eng ch.4): em prod exige JEFREY_EVENTBUS__HMAC_KEY len>=32,
senao RuntimeError. Sem auto-key, sem fallback allow. Deterministico:
json.dumps(sort_keys, separators) + timezone.utc + kid versionado + compare_digest.

Kid rotacao: JEFREY_EVENTBUS__HMAC_KEYS_JSON='{"v1":"<hex32>","v2":"<hex32>"}'
ou single JEFREY_EVENTBUS__HMAC_KEY + JEFREY_EVENTBUS__HMAC_KID=v1 (compat).
Dual-verify aceita v1 e v2 simultaneamente para nao quebrar Redis Streams.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import warnings
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class EventSigningError(Exception):
    pass


class InvalidSignatureError(EventSigningError):
    pass


class ExpiredMessageError(EventSigningError):
    pass


def _get_hmac_keys() -> Dict[str, str]:
    """Retorna dict kid->key. Suporta HMAC_KEYS_JSON ou single key + KID."""
    keys_json = os.getenv("JEFREY_EVENTBUS__HMAC_KEYS_JSON", "")
    if keys_json:
        try:
            keys: Dict[str, str] = json.loads(keys_json)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"JEFREY_EVENTBUS__HMAC_KEYS_JSON invalido: {e}") from e
        if not isinstance(keys, dict) or not keys:
            raise RuntimeError("JEFREY_EVENTBUS__HMAC_KEYS_JSON vazio ou nao-dict")
        for k, v in keys.items():
            if not isinstance(v, str) or len(v) < 32:
                is_prod = os.getenv("JEFREY_ENV", "dev") == "prod"
                if is_prod:
                    raise ValueError(f"HMAC key kid={k!r} len={len(v) if isinstance(v, str) else 0} <32 em prod")
                warnings.warn(f"HMAC key kid={k!r} len<32 fraco", UserWarning, stacklevel=2)
        return keys
    kid = os.getenv("JEFREY_EVENTBUS__HMAC_KID", "v1")
    key = os.getenv("JEFREY_EVENTBUS__HMAC_KEY", "")
    key_v2 = os.getenv("JEFREY_EVENTBUS__HMAC_KEY_V2", "")
    if key_v2:
        if not key or len(key) < 32:
            raise RuntimeError("JEFREY_EVENTBUS__HMAC_KEY ausente/<32 mas V2 definido — defina V1 tambem")
        if len(key_v2) < 32:
            raise ValueError("JEFREY_EVENTBUS__HMAC_KEY_V2 len<32")
        return {"v1": key, "v2": key_v2}
    if not key:
        raise RuntimeError(
            "JEFREY_EVENTBUS__HMAC_KEY ausente (C1a) — gere: openssl rand -hex 32 "
            "e defina JEFREY_EVENTBUS__HMAC_KEY (ou HMAC_KEYS_JSON) mesmo em dev"
        )
    if len(key) < 32:
        is_prod = os.getenv("JEFREY_ENV", "dev") == "prod"
        if is_prod:
            raise ValueError(f"JEFREY_EVENTBUS__HMAC_KEY len={len(key)} <32 em prod (C1a)")
        warnings.warn(f"JEFREY_EVENTBUS__HMAC_KEY len={len(key)} <32 fraco", UserWarning, stacklevel=2)
    return {kid: key}


def _get_hmac_key(kid: str | None = None) -> str:
    """Fail-closed: resolve key por kid. Em prod sem key => RuntimeError."""
    keys = _get_hmac_keys()
    if kid:
        if kid not in keys:
            raise RuntimeError(f"kid {kid!r} nao encontrado em HMAC keys (kids={list(keys)})")
        return keys[kid]
    default_kid = os.getenv("JEFREY_EVENTBUS__HMAC_KID", "v1")
    if default_kid in keys:
        return keys[default_kid]
    if len(keys) == 1:
        return next(iter(keys.values()))
    raise RuntimeError(f"JEFREY_EVENTBUS__HMAC_KID={default_kid!r} nao em HMAC_KEYS_JSON (kids={list(keys)})")


def _canonical_json(payload: Dict[str, Any]) -> str:
    """Deterministico: sort_keys + separators sem espaco."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sign_message(
    message: Dict[str, Any],
    user_id: str,
    hmac_key: Optional[str] = None,
    kid: str | None = None,
) -> Dict[str, Any]:
    """CIPHER-033 + kid versionado. HMAC = HMAC-SHA256(key[kid], user_id.timestamp.canonical)."""
    if not user_id:
        raise ValueError("user_id obrigatorio para isolamento (Axiom #2)")
    kid = kid or os.getenv("JEFREY_EVENTBUS__HMAC_KID", "v1")
    resolved_key = hmac_key or _get_hmac_key(kid)
    signed = message.copy()
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    signed["timestamp"] = timestamp
    signed["kid"] = kid
    signed["user_id"] = user_id
    canonical_keys = sorted(k for k in signed.keys() if k != "signature")
    canonical_payload = {k: signed[k] for k in canonical_keys}
    canonical_str = _canonical_json(canonical_payload)
    hmac_input = f"{user_id}.{timestamp}.{canonical_str}".encode("utf-8")
    signature = hmac.new(resolved_key.encode("utf-8"), hmac_input, hashlib.sha256).hexdigest()
    signed["signature"] = signature
    return signed


def _verify_with_key(signed_message: Dict[str, Any], hmac_key: str) -> bool:
    user_id = signed_message.get("user_id", "")
    timestamp = signed_message.get("timestamp", "")
    canonical_keys = sorted(k for k in signed_message.keys() if k != "signature")
    canonical_payload = {k: signed_message[k] for k in canonical_keys}
    canonical_str = _canonical_json(canonical_payload)
    hmac_input = f"{user_id}.{timestamp}.{canonical_str}".encode("utf-8")
    expected = hmac.new(hmac_key.encode("utf-8"), hmac_input, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signed_message.get("signature", ""), expected)


def verify_message(
    signed_message: Dict[str, Any],
    hmac_key: Optional[str] = None,
    tolerance_minutes: int = 5,
) -> Tuple[bool, Optional[str]]:
    """Dual-verify kid v1+v2, compare_digest, timezone-aware."""
    if "signature" not in signed_message:
        return False, "missing_signature_field"
    if "timestamp" not in signed_message:
        return False, "missing_timestamp_field"
    kid = signed_message.get("kid", "v0")
    user_id = signed_message.get("user_id")
    if not user_id:
        return False, "missing_user_id_field"
    timestamp = signed_message["timestamp"]
    try:
        msg_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if msg_time.tzinfo is None:
            msg_time = msg_time.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return False, "invalid_timestamp_format"
    now = datetime.now(timezone.utc)
    age = now - msg_time
    max_age = timedelta(minutes=tolerance_minutes)
    if age > max_age and age > timedelta(0):
        return False, f"expired_message_{int(age.total_seconds()/60)}min_old"
    if age < timedelta(0) and abs(age) > max_age:
        return False, "future_message_too_ahead"
    if hmac_key is not None:
        return (True, None) if _verify_with_key(signed_message, hmac_key) else (False, "invalid_signature")
    keys = _get_hmac_keys()
    if kid == "v0":
        warnings.warn("mensagem sem kid (v0 compat) — rotacione para v1/v2", DeprecationWarning, stacklevel=2)
        try:
            from src.jefrey.core.metrics import EVENTBUS_KID_LEGACY_TOTAL
            EVENTBUS_KID_LEGACY_TOTAL.inc()
        except Exception as _e:
            logger.debug("signing legacy verify falhou: %s", _e)
        for _, key in keys.items():
            if _verify_with_key(signed_message, key):
                return True, None
        return False, "invalid_signature"
    expected_key = keys.get(kid)
    if expected_key is None:
        return False, f"unknown_kid_{kid}"
    if _verify_with_key(signed_message, expected_key):
        return True, None
    return False, "invalid_signature"
