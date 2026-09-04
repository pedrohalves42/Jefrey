"""Auth dev-token — Axiom #1/#3 FAIL-CLOSED, CIPHER-021, Security Eng cap4.

POST /auth/dev-token so JEFREY_ENV!=prod. Sem auto-key, sem stub em prod (fail-closed).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from src.jefrey.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/dev-token")
async def dev_token(request: Request):
    """Retorna Bearer dev para wiring local. FAIL-CLOSED em prod (CIPHER-021, Axiom #3)."""
    cfg = get_settings()
    # dupla guarda: env prod OU debug false + env != dev => 403
    if cfg.is_prod:
        raise HTTPException(status_code=403, detail="dev-token desabilitado em prod (CIPHER-021)")
    if not cfg.debug and cfg.env != "dev":
        raise HTTPException(status_code=403, detail="dev-token desabilitado fora de dev")

    secret = cfg.api.secret_key
    if not secret or len(secret) < 16 or "CHANGE_ME" in secret:
        raise HTTPException(
            status_code=500,
            detail="secret_key nao configurado para dev-token (configure JEFREY_API__SECRET_KEY >=32)",
        )

    # nunca loga token raw (CIPHER-010)
    logger.info("dev-token emitido env=%s", cfg.env)
    return {"token": secret, "user_id": "demo", "expires_in": 86400, "env": cfg.env}
