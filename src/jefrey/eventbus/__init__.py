"""
CIPHER-033: EventBus Integration

Exports for EventBus message signing, publishing, and subscription.
Provides per-tenant event isolation (Axiom #2) and HMAC-SHA256 message integrity (CIPHER-033).
"""

from src.jefrey.eventbus.signing import sign_message, verify_message, _get_hmac_key  # noqa: F401

__all__ = [
    "sign_message",
    "verify_message",
    "_get_hmac_key",
]