"""Auth — Axiom #1/#3 FAIL-CLOSED, CIPHER-021/031/035, Security Eng cap4.

POST /auth/dev-token so JEFREY_ENV!=prod. Sem auto-key, stub em prod.
Além disso: login OAuth2 Google (CIPHER-031) com PKCE flow completo.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import time
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode
from typing import Optional

import httpx
from fastapi import APIRouter, Request, HTTPException, status

from src.jefrey.core.config import get_settings

_GOOGLE_STATE_TTL_S = 600
_google_states: dict[str, tuple[str, float]] = {}  # state -> (code_verifier, expira)


def _remember_google_state(state: str, verifier: str) -> None:
    now = time.time()
    _google_states[state] = (verifier, now + _GOOGLE_STATE_TTL_S)
    for k in [k for k, (_, exp) in _google_states.items() if exp < now]:
        _google_states.pop(k, None)
    while len(_google_states) > 50:
        _google_states.pop(next(iter(_google_states)))


def _consume_google_state(state: str) -> Optional[str]:
    """Devolve o code_verifier se o state existe, nao expirou e ainda nao foi usado; senao None."""
    entry = _google_states.pop(state or "", None)
    if entry is None or entry[1] < time.time():
        return None
    return entry[0]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Credenciais Google (carregadas via get_settings) ──────────────────────────────
def _get_oauth_credentials():
    """Credenciais do app Google: a fonte unica e core.google_oauth.credentials() (variavel de ambiente ou arquivo salvo na tela);
    a configuracao do programa e so o ultimo recurso."""
    from src.jefrey.core.google_oauth import credentials as _saved

    cfg = get_settings()
    found = _saved() or {}
    return {
        "client_id": found.get("client_id") or getattr(getattr(cfg, "oauth", None), "google_client_id", None),
        "client_secret": found.get("client_secret") or getattr(getattr(cfg, "oauth", None), "google_client_secret", None),
        "redirect_uri": os.getenv("JEFREY_OAUTH__REDIRECT_URIS", "http://localhost:8000/auth/google/callback"),
        "aud": os.getenv("JEFREY_OAUTH__AUD", "jefrey"),
        "iss": os.getenv("JEFREY_OAUTH__ISS", "https://accounts.google.com"),
    }


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
            detail="O Jefrey ainda não está preparado para abrir sessão. Reinstale ou fale com quem te entregou o Jefrey.",
        )

    # CIPHER-302: antes devolvia a propria JEFREY_API__SECRET_KEY como token (master key exposta
    # num endpoint publico) e ignorava o user_id pedido. Agora emite um JWT HS256 por usuario.
    import re as _re
    import jwt  # PyJWT
    try:
        body = await request.json()
    except Exception:
        body = {}
    raw_uid = str((body or {}).get("user_id") or request.headers.get("X-User-Id") or "demo").strip()
    if not _re.fullmatch(r"[A-Za-z0-9_.@\-]{1,64}", raw_uid) or raw_uid in ("system", "service", "anonymous"):
        raise HTTPException(status_code=400, detail="user_id invalido (1-64 chars: letras, numeros, _ . @ -)")
    ttl = 86400
    now = int(time.time())
    token = jwt.encode({"sub": raw_uid, "iss": "jefrey-dev", "iat": now, "exp": now + ttl, "scope": "dev"},
                       secret, algorithm="HS256")
    # nunca loga token raw (CIPHER-010)
    logger.info("dev-token emitido env=%s user=%s", cfg.env, raw_uid)
    return {"access_token": token, "token": token, "token_type": "Bearer", "user_id": raw_uid,
            "expires_in": ttl, "env": cfg.env}


@router.get("/google/login")
async def google_login(request: Request = None):
    """Iniciar fluxo OAuth2 com Google.

    Redireciona o usuário para a tela de consentimento do Google.
    O usuário retorna para /auth/google/callback com o authorization code.
    Gera state CSRF (CIPHER-031) para mitigar CSRF.
    """
    creds = _get_oauth_credentials()
    if not creds["client_id"] or not creds["client_secret"]:
        raise HTTPException(
            status_code=503,
            detail="O login com o Google ainda não foi liberado nesta cópia. Em Conexões > Google, cole o ID e a chave, ou fale com quem te entregou o Jefrey."
        )
    
    # state CSRF + PKCE (S256): guardados no servidor, de uso unico, e conferidos no retorno
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    _remember_google_state(state, verifier)
    params = {
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "client_id": creds["client_id"],
        "redirect_uri": creds["redirect_uri"],
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
    # o botao "Conectar Google" da tela usa este mesmo endereco de retorno quando o app do Google so tem ele registrado
    from src.jefrey.core import google_oauth as _G

    _st = request.query_params.get("state") or ""
    if _G.has_state(_st):
        from src.jefrey.api.google_connect import finish

        return await finish(request.query_params.get("code") or "", _st, request.query_params.get("error") or "")
    creds = _get_oauth_credentials()
    if not creds["client_id"] or not creds["client_secret"]:
        raise HTTPException(
            status_code=503,
            detail="O login com o Google ainda não foi liberado nesta cópia. Em Conexões > Google, cole o ID e a chave, ou fale com quem te entregou o Jefrey."
        )
    
    # state CSRF: obrigatorio e de uso unico (antes era so registrado em log)
    code_verifier = _consume_google_state(request.query_params.get("state") or "")
    if code_verifier is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Login recusado: state invalido, expirado ou ja usado")
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
                "client_id": creds["client_id"],
                "client_secret": creds["client_secret"],
                "redirect_uri": creds["redirect_uri"],
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
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
                logger.info("id_token recebido iss=%s", payload.get("iss"))
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
                logger.info("userinfo OK")
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
            intel = _introspect(access_token, client_id=creds["client_id"])
            if intel.active and intel.user_id:
                # se introspect local ativo, usa como complemento (caso token proprio)
                user_id = intel.user_id or user_id
                logger.debug("introspect local ativo user_id=%s", intel.user_id)
        except Exception as e:
            logger.debug("introspect local skip (token Google nao e JWT local): %s", e)

        # 2d) Salvar token OAuth2 no PostgreSQL por user_id (CIPHER-001 - multi-tenant)
        try:
            from src.jefrey.core.db import get_db
            from src.jefrey.core.models import OAuthToken
            from datetime import datetime, timedelta
            
            expires_seconds = token_data.get("expires_in", 3600)
            expires_at = datetime.utcnow() + timedelta(seconds=expires_seconds) if expires_seconds else None
            
            with get_db() as session:
                # Upsert token (delete existente + insert novo)
                session.query(OAuthToken).filter(
                    OAuthToken.user_id == user_id,
                    OAuthToken.provider == "google"
                ).delete()
                
                token_record = OAuthToken(
                    user_id=user_id,
                    provider="google",
                    access_token=access_token,
                    refresh_token=refresh_token,
                    token_type=token_data.get("token_type", "Bearer"),
                    expires_at=expires_at,
                    scopes=token_data.get("scope", "").split(),
                    email=email,
                )
                session.add(token_record)
                session.commit()
                logger.info("OAuth token salvo no PostgreSQL user_id=%s provider=google", user_id)
        except Exception as e:
            logger.error("Falha ao salvar OAuth token no PostgreSQL: %s", e)
            # Continua mesmo se falhar o salvamento (soft-fail)

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


# ── Endpoint 3: Obter token OAuth2 por user_id (CIPHER-001) ────────────────

@router.get("/oauth-token/{provider}")
async def get_oauth_token(request: Request, provider: str):
    """Obter token OAuth2 salvo por user_id e provider (CIPHER-001).
    
    Usado pelas skills Google (calendar, email, drive) para obter token
    específico do usuário atual.
    """
    from src.jefrey.core.db import get_db
    from src.jefrey.core.models import OAuthToken
    
    # Extrair user_id do header de autenticação (Bearer token)
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    
    # Em prod, validar o Bearer token com o OAuth2 local. Em dev, aceitar qualquer.
    cfg = get_settings()
    creds = _get_oauth_credentials()
    if cfg.is_prod:
        from src.jefrey.oauth2.introspect import introspect_token as _introspect
        try:
            token = auth_header.replace("Bearer ", "")
            intel = _introspect(token, client_id=creds["client_id"])
            if not intel.active:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
            user_id = intel.user_id
        except Exception as e:
            logger.warning("OAuth introspection failed: %s", e)
            raise HTTPException(status_code=401, detail="Authentication failed")
    else:
        # Em dev, usar user_id do token ou "demo"
        user_id = "demo"
    
    # Buscar token OAuth2 específico
    with get_db() as session:
        token_record = session.query(OAuthToken).filter(
            OAuthToken.user_id == user_id,
            OAuthToken.provider == provider
        ).first()
        
        if not token_record:
            raise HTTPException(
                status_code=404,
                detail=f"No OAuth token found for user_id={user_id} provider={provider}. Please authenticate with Google first."
            )
        
        # Verificar se o token expirou e tentar refresh (CIPHER-001 fix)
        if token_record.expires_at and token_record.expires_at < datetime.utcnow():
            if token_record.refresh_token:
                # Implementar refresh token
                try:
                    async with httpx.AsyncClient() as client:
                        refresh_resp = await client.post(
                            "https://oauth2.googleapis.com/token",
                            data={
                                "refresh_token": token_record.refresh_token,
                                "client_id": creds["client_id"],
                                "client_secret": creds["client_secret"],
                                "grant_type": "refresh_token",
                            },
                            timeout=10.0,
                        )
                        if refresh_resp.status_code == 200:
                            refresh_data = refresh_resp.json()
                            new_access_token = refresh_data.get("access_token")
                            new_expires_in = refresh_data.get("expires_in", 3600)
                            new_expires_at = datetime.utcnow() + timedelta(seconds=new_expires_in)
                            
                            # Atualizar no PostgreSQL
                            token_record.access_token = new_access_token
                            token_record.expires_at = new_expires_at
                            session.commit()
                            logger.info("OAuth token refresh sucesso user_id=%s provider=%s", user_id, provider)
                            
                            return {
                                "user_id": token_record.user_id,
                                "provider": token_record.provider,
                                "access_token": token_record.access_token,
                                "token_type": token_record.token_type,
                                "expires_at": token_record.expires_at.isoformat() if token_record.expires_at else None,
                                "email": token_record.email,
                                "refreshed": True,
                            }
                        else:
                            logger.warning("OAuth token refresh falhou user_id=%s provider=%s status=%s", user_id, provider, refresh_resp.status_code)
                            raise HTTPException(status_code=401, detail="OAuth token expired and refresh failed. Please re-authenticate.")
                except Exception as e:
                    logger.warning("OAuth token refresh exception user_id=%s provider=%s: %s", user_id, provider, e)
                    raise HTTPException(status_code=401, detail="OAuth token expired and refresh failed. Please re-authenticate.")
            else:
                raise HTTPException(status_code=401, detail="OAuth token expired and no refresh token available.")
        
        return {
            "user_id": token_record.user_id,
            "provider": token_record.provider,
            "access_token": token_record.access_token,
            "token_type": token_record.token_type,
            "expires_at": token_record.expires_at.isoformat() if token_record.expires_at else None,
            "email": token_record.email,
        }


# ── Endpoint 4: Salvar token OAuth2 manualmente (CIPHER-001) ────────────────

@router.post("/oauth-token/{provider}")
async def save_oauth_token(request: Request, provider: str, token_data: dict):
    """Salvar token OAuth2 manualmente por user_id e provider (CIPHER-001).
    
    Usado para testes ou quando o usuário já tem um token OAuth2 salvo.
    """
    from src.jefrey.core.db import get_db
    from src.jefrey.core.models import OAuthToken
    from datetime import datetime, timedelta
    
    # Extrair user_id do header de autenticação
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    
    cfg = get_settings()
    creds = _get_oauth_credentials()
    if cfg.is_prod:
        from src.jefrey.oauth2.introspect import introspect_token as _introspect
        try:
            token = auth_header.replace("Bearer ", "")
            intel = _introspect(token, client_id=creds["client_id"])
            if not intel.active:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
            user_id = intel.user_id
        except Exception as e:
            logger.warning("OAuth introspection failed: %s", e)
            raise HTTPException(status_code=401, detail="Authentication failed")
    else:
        user_id = token_data.get("user_id", "demo")
    
    # Extrair dados do token
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    email = token_data.get("email")
    expires_in = token_data.get("expires_in", 3600)
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in) if expires_in else None
    
    if not access_token:
        raise HTTPException(status_code=400, detail="Missing access_token")
    
    try:
        with get_db() as session:
            # Upsert token
            session.query(OAuthToken).filter(
                OAuthToken.user_id == user_id,
                OAuthToken.provider == provider
            ).delete()
            
            token_record = OAuthToken(
                user_id=user_id,
                provider=provider,
                access_token=access_token,
                refresh_token=refresh_token,
                token_type=token_data.get("token_type", "Bearer"),
                expires_at=expires_at,
                scopes=token_data.get("scopes", []),
                email=email,
            )
            session.add(token_record)
            session.commit()
            logger.info("OAuth token salvo manualmente user_id=%s provider=%s", user_id, provider)
            
            return {
                "user_id": user_id,
                "provider": provider,
                "email": email,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "message": "OAuth token saved successfully",
            }
    except Exception as e:
        logger.error("Falha ao salvar OAuth token: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to save OAuth token: {e}")