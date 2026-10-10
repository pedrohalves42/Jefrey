"""Credenciais do Google (OAuth2) por pessoa, para as ferramentas de Agenda, Gmail e Drive.

Antes cada ferramenta tinha a sua copia deste codigo (~150 linhas x 3). Aqui fica uma so: o token da pessoa vem do banco
(protegido), e so se nao houver token entra o arquivo de credenciais local (uma pessoa so, sem isolamento).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _unprotect(v):
    from src.jefrey.core.secret_store import unprotect

    return unprotect(v)


def _protect(v):
    from src.jefrey.core.secret_store import protect

    return protect(v)


class GoogleCredentials:
    """`provider` e o nome gravado no banco (google_calendar, google_drive, gmail); `config_attr`, o trecho de `integrations` na configuracao."""

    def __init__(self, provider: str, config_attr: str, scopes: list[str]):
        self.provider, self.config_attr, self.scopes = provider, config_attr, list(scopes)
        self.cache: dict[str, Any] = {}  # credenciais por pessoa (CIPHER-001: nunca misturar pessoas)

    # ---- aplicativo (client id/secret) ----
    def _client(self, key: str) -> str:
        from src.jefrey.core.google_oauth import credentials as _gc

        c = _gc()
        if c:
            return c[key]
        try:
            from src.jefrey.core.config import get_settings

            return getattr(getattr(get_settings().integrations, self.config_attr), key)
        except Exception:
            return os.getenv("JEFREY_OAUTH__CLIENT_ID" if key == "client_id" else "JEFREY_OAUTH__CLIENT_SECRET", "")

    @staticmethod
    def _request():
        try:
            from google.auth.transport.requests import Request

            return Request()
        except Exception:
            return None

    # ---- credenciais da pessoa ----
    def for_user(self, user_id: Optional[str] = None):
        """Credenciais OAuth2 do banco para `user_id` (isolamento multi-pessoa). Sem pessoa ou sem token: arquivo local, se houver."""
        if not user_id:
            logger.warning("CIPHER-001: user_id não fornecido - usando fallback single-tenant (não isolado)")
            return self._fallback()
        creds = self.cache.get(user_id)
        if creds and creds.valid:
            return creds
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(self._request())
                logger.info("CIPHER-001: Token OAuth2 refresh para user_id=%s", user_id)
                return creds
            except Exception as e:
                logger.warning("CIPHER-001: Token refresh falhou user_id=%s: %s", user_id, e)
        try:
            from google.oauth2.credentials import Credentials

            from src.jefrey.core.db import get_db
            from src.jefrey.core.models import OAuthToken

            with get_db() as session:
                rec = session.query(OAuthToken).filter(OAuthToken.user_id == user_id, OAuthToken.provider == self.provider).first()
                if not rec:
                    logger.warning("CIPHER-001: No OAuth token found for user_id=%s provider=%s - usando fallback", user_id, self.provider)
                    return self._fallback()
                creds = Credentials(
                    token=_unprotect(rec.access_token),
                    refresh_token=_unprotect(rec.refresh_token) if rec.refresh_token else None,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=self._client("client_id"),
                    client_secret=self._client("client_secret"),
                    scopes=rec.scopes or self.scopes,
                )
                if rec.expires_at:
                    creds.expiry = rec.expires_at
                if creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(self._request())
                        rec.access_token = _protect(creds.token)
                        rec.expires_at = creds.expiry
                        session.commit()
                        logger.info("CIPHER-001: Token OAuth2 refresh + atualizado no banco user_id=%s", user_id)
                    except Exception as e:
                        logger.warning("CIPHER-001: Token refresh falhou user_id=%s: %s", user_id, e)
                self.cache[user_id] = creds
                logger.info("CIPHER-001: OAuth token carregado do banco user_id=%s", user_id)
                return creds
        except Exception as e:
            logger.error("CIPHER-001: Falha ao carregar OAuth token do banco: %s", e)
            return self._fallback()

    # ---- arquivo local (uma pessoa so) ----
    def _fallback(self):
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError:
            logger.warning("google-api-python-client nao instalado")
            return None
        from src.jefrey.core.config import get_settings

        cfg = getattr(get_settings().integrations, self.config_attr)
        creds_file, token_file = Path(cfg.credentials_file), Path(cfg.token_file)
        if not creds_file.exists():
            logger.warning("Credenciais Google (%s) nao encontradas: %s", self.provider, creds_file)
            return None
        try:
            creds = None
            if token_file.exists():
                creds = Credentials.from_authorized_user_file(str(token_file), self.scopes)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                    except Exception as e:
                        logger.warning("Google token refresh falhou: %s", type(e).__name__)
                        return None
                else:
                    creds = InstalledAppFlow.from_client_secrets_file(str(creds_file), self.scopes).run_local_server(port=0)
                token_file.parent.mkdir(parents=True, exist_ok=True)
                try:
                    token_file.parent.chmod(0o700)
                except Exception as _e:
                    logger.debug("ignorado (google_credentials): %s", type(_e).__name__)
                with open(token_file, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
                try:
                    token_file.chmod(0o600)
                except Exception as _e:
                    logger.debug("ignorado (google_credentials): %s", type(_e).__name__)
            return creds
        except Exception as e:
            logger.warning("Google initialize falhou: %s", type(e).__name__)
            return None
