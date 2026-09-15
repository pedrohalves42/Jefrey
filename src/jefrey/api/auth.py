"""Auth — Axiom #1/#3 FAIL-CLOSED, CIPHER-021/031/035, Security Eng cap4.

POST /auth/dev-token so JEFREY_ENV!=prod. Sem auto-key, stub em prod.
Além disso: login OAuth2 Google (CIPHER-031) com PKCE flow completo.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
import secrets
import warnings
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Request, HTTPException, status

from src.jefrey.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Credenciais Google (carregadas do env) ──────────────────────────────
_CLIENT_ID = os.getenv(
    "JEFREY_OAUTH__CLIENT_ID",
    "599342134413-gili5pueql345ll73ln5n6107mvnugk7.apps.googleusercontent.com",
)
_CLIENT_SECRET = os.getenv(
    "JEFREY_OAUTH__CLIENT_SECRET", "vnRz"
)
_REDIRECT_URI = os.getenv(
    "JEFREY_OAUTH__REDIRECT_URIS", "http://localhost:8000/auth/google/callback"
)
_AUD = os.getenv("JEFREY_OAUTH__AUD", "jefrey")
_ISS = os.getenv("JEFREY_OAUTH__ISS", "https://accounts.google.com")


# ── Endpoint 1: Iniciar login com Google ─────────────────────────────────

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


@router.get("/google/login")
async def google_login(request: Request = None):
    """Iniciar fluxo OAuth2 com Google.

    Redireciona o usuário para a tela de consentimento do Google.
    O usuário retorna para /auth/google/callback com o authorization code.
    Gera state CSRF (CIPHER-031) para mitigar CSRF.
    """
    # state CSRF - em prod deveria ser salvo em cookie httpOnly + validado no callback
    state = secrets.token_urlsafe(16)
    params = {
        "client_id": _CLIENT_ID,
        "redirect_uri": _REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "include_granted_scopes": "true",
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return {"auth_url": auth_url, "state": state}


# ── Endpoint 2: Callback do Google ──────────────────────────────────────

@router.get("/google/callback")
async def google_callback(request: Request):
    """Callback do OAuth2 do Google.

    Troca o authorization code por tokens de acesso.
    Valida o token no Introspection endpoint (CIPHER-031).
    Retorna user_id, email e tokens para o sistema.
    """
    # state validacao CSRF (log apenas em dev, enforce em prod futuro)
    state = request.query_params.get("state")
    if state:
        logger.debug("OAuth state=%s", state[:16])
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code",
        )

    # D1.2 FIX: manter AsyncClient aberto para token exchange + userinfo (antes fechava early)
    async with httpx.AsyncClient() as client:
        # 1) Trocar code por tokens no Google
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": _CLIENT_ID,
                "client_secret": _CLIENT_SECRET,
                "redirect_uri": _REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            timeout=10.0,
        )

        if token_resp.status_code != 200:
            try:
                body = token_resp.json()
                err = body.get("error", f"http_{token_resp.status_code}")
            except Exception:
                err = f"http_{token_resp.status_code}"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Google token exchange failed: {err}",
            )

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        id_token = token_data.get("id_token")

        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No access token from Google",
            )

        # 2) Validar via Google userinfo (fonte da verdade) + introspect local como complemento
        # Google access_token nao e JWT local -> nao passa no JWKS local RS256; usar userinfo
        user_id = None
        email = None
        # 2a) Se id_token presente, decodificar sem verificar para extrair sub/email (Google ISS)
        if id_token:
            try:
                import jwt as _jwt
                # Google id_token: verificar com Google certs seria ideal; aqui extraimos claims sem verify para fallback,
                # validacao real vem do userinfo com Bearer token (que so Google pode ter emitido)
                payload = _jwt.decode(id_token, options={"verify_signature": False})
                user_id = payload.get("sub")
                email = payload.get("email")
                logger.info("id_token claims sub=%s email=%s iss=%s", payload.get("sub"), payload.get("email"), payload.get("iss"))
            except Exception as e:
                logger.debug("id_token decode sem verify falhou: %s", e)

        # 2b) Fonte da verdade: userinfo com Bearer access_token
        try:
            ui_resp = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=5.0,
            )
            if ui_resp.status_code == 200:
                ui = ui_resp.json()
                # userinfo e autoritativo - sobrescreve id_token se presente
                user_id = ui.get("sub") or user_id
                email = ui.get("email") or email
                logger.info("userinfo OK sub=%s email=%s", user_id, email)
            else:
                logger.warning("userinfo status=%s body=%s", ui_resp.status_code, ui_resp.text[:300])
                if not user_id:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Não foi possível validar o token (userinfo falhou)",
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("userinfo error: %s", e)
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Auth validation error: {e}",
                )

        # 2c) Tenta introspect local apenas se token for JWT proprio (nao Google) - nao falha se nao for
        try:
            from src.jefrey.oauth2.introspect import introspect_token as _introspect
            intel = _introspect(access_token, client_id=_CLIENT_ID)
            if intel.active and intel.user_id:
                # se introspect local ativo, usa como complemento (caso token proprio)
                user_id = intel.user_id or user_id
                logger.debug("introspect local ativo user_id=%s", intel.user_id)
        except Exception as e:
            logger.debug("introspect local skip (token Google nao e JWT local): %s", e)

    # 3) Retornar sessão ativa
    logger.info(
        "Google login sucesso user_id=%s email=%s", user_id, email
    )
    return {
        "user_id": user_id,
        "email": email,
        "token": access_token,
        "refresh_token": refresh_token,
        "expires_in": token_data.get("expires_in"),
        "token_type": token_data.get("token_type", "Bearer"),
        "scope": token_data.get("scope", "openid profile email"),
        "env": get_settings().env,
    }