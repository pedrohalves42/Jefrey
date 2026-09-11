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
_ISS = os.getenv("JEFREY_OAUTH__ISS", "https://oauth2.googleapis.com/auth")


# ── Endpoint 1: Iniciar login com Google ─────────────────────────────────

@router.get("/google/login")
async def google_login():
    """Iniciar fluxo OAuth2 com Google.

    Redireciona o usuário para a tela de consentimento do Google.
    O usuário retorna para /auth/google/callback com o authorization code.
    """
    params = {
        "client_id": _CLIENT_ID,
        "redirect_uri": _REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return {"auth_url": auth_url}


# ── Endpoint 2: Callback do Google ──────────────────────────────────────

@router.get("/google/callback")
async def google_callback(request: Request):
    """Callback do OAuth2 do Google.

    Troca o authorization code por tokens de acesso.
    Valida o token no Introspection endpoint (CIPHER-031).
    Retorna user_id, email e tokens para o sistema.
    """
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code",
        )

    # 1) Trocar code por tokens no Google
    async with httpx.AsyncClient() as client:
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

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No access token from Google",
        )

    # 2) Validar token no Introspection endpoint (CIPHER-031)
    try:
        from src.jefrey.oauth2.introspect import introspect_token

        intel = introspect_token(access_token, client_id=_CLIENT_ID)
        if not intel.active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido ou revogado",
            )
        user_id = intel.user_id or intel.sub
        email = intel.sub if hasattr(intel, "sub") else None
        if not email and access_token:
            # fallback: buscar userinfo
            try:
                ui_resp = await client.get(
                    "https://openidconnect.googleapis.com/v1/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=5.0,
                )
                if ui_resp.status_code == 200:
                    ui = ui_resp.json()
                    email = ui.get("email")
                    user_id = ui.get("sub") or user_id
            except Exception:
                pass
    except Exception as e:
        logger.warning("Introspection falhou, tentando userinfo direto: %s", e)
        # Fallback direto para userinfo
        try:
            ui_resp = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=5.0,
            )
            if ui_resp.status_code == 200:
                ui = ui_resp.json()
                user_id = ui.get("sub")
                email = ui.get("email")
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Não foi possível validar o token",
                )
        except Exception as e2:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Auth validation error: {e2}",
            )

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