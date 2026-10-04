"""P6 — HMAC Key Rotation Endpoint (CIPHER-033).

Endpoint POST /api/signing/rotate-hmac
Gera nova chave HMAC e atualiza a configuração de kids para dual-verify.
Essencial para compliance de key rotation policies sem interromper
as streams Redis que podem estar processando mensagens assinadas com a key antiga.
"""
from __future__ import annotations

import os
import logging
from fastapi import Request, APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.jefrey.eventbus.signing import _get_hmac_keys, rotate_hmac_key as _rotate_hmac_key_internal

logger = logging.getLogger(__name__)

router = APIRouter(tags=["signing"])


class RotateHMACKeyResponse(BaseModel):
    """Response model for HMAC key rotation."""
    success: bool = True
    new_kid: str
    new_key_shown: str = Field(default="", description="First 8 chars shown for verification, rest masked for security")
    total_keys: int
    message: str = Field(default="", description="Optional descriptive message")


@router.post(
    "/rotate-hmac",
    response_model=RotateHMACKeyResponse,
    summary="Rotate HMAC Key",
    description="""Rotate the HMAC key for event bus signing.

    Behavior:
    - Multi-key mode (JEFREY_EVENTBUS__HMAC_KEYS_JSON): adds new key as next kid version
    - Single key mode: promotes current key to V1, new key becomes V2
    - Dual-verify remains active during and after rotation (v1+v2 both valid)
    - Redis streams continue processing without interruption

    Returns:
        new_kid: The kid version that was added/rotated
        new_key_shown: First 8 chars of the new key (rest masked for security)
        total_keys: Total number of keys now in the rotation set
        message: Descriptive status message
    """,
)
async def rotate_hmac_key_endpoint(request: Request) -> RotateHMACKeyResponse:
    """Rotate HMAC key for event bus signing with dual-verify support."""
    # CIPHER-301: antes era publico; agora so o token de servico (secret_key) pode girar chaves
    if getattr(request.state, "oauth2_client", None) != "configured-secret":
        raise HTTPException(status_code=403, detail="apenas o token de servico pode girar chaves HMAC")
    try:
        new_key, new_kid = _rotate_hmac_key_internal()
        
        # Get current keys count
        keys = _get_hmac_keys()
        total_keys = len(keys)
        
        # Show first 8 chars for verification, mask the rest
        new_key_shown = new_key[:8] + "..." + new_key[-4:] if len(new_key) > 12 else new_key
        
        response = RotateHMACKeyResponse(
            success=True,
            new_kid=new_kid,
            new_key_shown=new_key_shown,
            total_keys=total_keys,
            message=f"HMAC key rotated successfully. New kid: {new_kid}. Dual-verify active."
        )
        
        logger.info(f"HMAC key rotated: kid={new_kid}, total_keys={total_keys}")
        return response
        
    except RuntimeError as e:
        logger.error(f"HMAC key rotation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"HMAC key rotation error: {str(e)}"
        )
    except ValueError as e:
        logger.error(f"HMAC key rotation validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"HMAC key rotation validation error: {str(e)}"
        )


@router.get(
    "/hmac-status",
    summary="HMAC Status",
    description="Check current HMAC key configuration and kids available for dual-verify.",
)
async def hmac_status() -> dict:
    """Get current HMAC key status and kids available."""
    keys = _get_hmac_keys()
    kid = os.getenv("JEFREY_EVENTBUS__HMAC_KID", "v1")
    
    return {
        "current_kid": kid,
        "total_keys": len(keys),
        "keys_available": list(keys.keys()),
        # CIPHER-301: nunca expor material de chave (antes vazava a chave v1 inteira em env_hmac_keys_json)
        "env_hmac_key_set": bool(os.getenv("JEFREY_EVENTBUS__HMAC_KEY")),
        "env_hmac_keys_json_set": bool(os.getenv("JEFREY_EVENTBUS__HMAC_KEYS_JSON")),
        "env_is_prod": os.getenv("JEFREY_ENV", "dev") == "prod",
        "dual_verify_active": len(keys) >= 2,
    }