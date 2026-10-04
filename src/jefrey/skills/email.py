"""Skill: E-mail (Gmail) - OAuth multi-tenant (CIPHER-001 fix)."""
from __future__ import annotations
from typing import Final
import logging
from pathlib import Path

from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool
from src.jefrey.core.config import get_settings

logger = logging.getLogger(__name__)


def _unprotect(v):
    from src.jefrey.core.secret_store import unprotect
    return unprotect(v)


def _protect(v):
    from src.jefrey.core.secret_store import protect
    return protect(v)

class EmailSkill(SkillBase):
    metadata = SkillMetadata(
        name="email",
        description="Gerencia Gmail (ler, enviar, organizar, buscar) - OAuth multi-tenant com isolamento por user_id",
        tags=["email", "gmail", "communication", "productivity"],
        requires_auth=True,
        enabled_by_default=True,  # Reabilitado após implementação multi-tenant
        config_schema={
            "type": "object",
            "properties": {
                "credentials_file": {"type": "string", "description": "Caminho do client_secret.json"},
                "token_file": {"type": "string", "description": "Caminho do token salvo"},
            },
        },
    )

    SCOPES: Final[list[str]] = ["https://www.googleapis.com/auth/gmail.modify"]

    def __init__(self):
        super().__init__()
        self._service = None
        self._creds = None
        self._token_cache = {}  # Cache de credenciais por user_id (CIPHER-001 fix)

    def _get_credentials_for_user(self, user_id: str | None = None):
        """Obtém credenciais OAuth2 do PostgreSQL para um user_id específico (CIPHER-001 fix)."""
        if not user_id:
            logger.warning("CIPHER-001: user_id não fornecido - usando fallback single-tenant (não isolado)")
            return self._get_fallback_credentials()
        
        # Verificar cache primeiro
        if user_id in self._token_cache:
            creds = self._token_cache[user_id]
            if creds and creds.valid:
                return creds
            elif creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(self._get_request())
                    logger.info("CIPHER-001: Token OAuth2 refresh para user_id=%s", user_id)
                    return creds
                except Exception as e:
                    logger.warning("CIPHER-001: Token refresh falhou user_id=%s: %s", user_id, e)
        
        # Buscar do PostgreSQL
        try:
            from src.jefrey.core.db import get_db
            from src.jefrey.core.models import OAuthToken
            from google.oauth2.credentials import Credentials
            
            with get_db() as session:
                token_record = session.query(OAuthToken).filter(
                    OAuthToken.user_id == user_id,
                    OAuthToken.provider == "gmail"
                ).first()
                
                if not token_record:
                    logger.warning("CIPHER-001: No OAuth token found for user_id=%s provider=google - usando fallback", user_id)
                    return self._get_fallback_credentials()
                
                creds = Credentials(
                    token=_unprotect(token_record.access_token),
                    refresh_token=_unprotect(token_record.refresh_token) if token_record.refresh_token else None,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=self._get_client_id(),
                    client_secret=self._get_client_secret(),
                    scopes=token_record.scopes or self.SCOPES,
                )
                
                if token_record.expires_at:
                    creds.expiry = token_record.expires_at
                
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(self._get_request())
                        token_record.access_token = _protect(creds.token)
                        token_record.expires_at = creds.expiry
                        session.commit()
                        logger.info("CIPHER-001: Token OAuth2 refresh + atualizado no PostgreSQL user_id=%s", user_id)
                    except Exception as e:
                        logger.warning("CIPHER-001: Token refresh falhou user_id=%s: %s", user_id, e)
                
                self._token_cache[user_id] = creds
                logger.info("CIPHER-001: OAuth token carregado do PostgreSQL user_id=%s email=%s", user_id, token_record.email)
                return creds
        except Exception as e:
            logger.error("CIPHER-001: Falha ao carregar OAuth token do PostgreSQL: %s", e)
            return self._get_fallback_credentials()
    
    def _get_client_id(self):
        from src.jefrey.core.google_oauth import credentials as _gc
        _c = _gc()
        if _c:
            return _c['client_id']
        return self._get_client_id_settings()

    def _get_client_id_settings(self):
        try:
            from src.jefrey.core.config import get_settings
            return get_settings().integrations.gmail.client_id
        except Exception:
            import os
            return os.getenv("JEFREY_OAUTH__CLIENT_ID", "")
    
    def _get_client_secret(self):
        from src.jefrey.core.google_oauth import credentials as _gc
        _c = _gc()
        if _c:
            return _c['client_secret']
        return self._get_client_secret_settings()

    def _get_client_secret_settings(self):
        try:
            from src.jefrey.core.config import get_settings
            return get_settings().integrations.gmail.client_secret
        except Exception:
            import os
            return os.getenv("JEFREY_OAUTH__CLIENT_SECRET", "")
    
    def _get_request(self):
        try:
            from google.auth.transport.requests import Request
            return Request()
        except Exception:
            return None

    def _get_fallback_credentials(self):
        """Fallback para credenciais do filesystem (single-tenant, não isolado)."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError:
            logger.warning("google-api-python-client nao instalado")
            return None
        cfg = get_settings().integrations.gmail
        creds_file = Path(cfg.credentials_file)
        token_file = Path(cfg.token_file)
        if not creds_file.exists():
            logger.warning(f"Credenciais Gmail nao encontradas: {creds_file}")
            return None
        try:
            if token_file.exists():
                creds = Credentials.from_authorized_user_file(str(token_file), self.SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                    except Exception as e:
                        logger.warning(f"Gmail token refresh falhou: {type(e).__name__}")
                        return None
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), self.SCOPES)
                    creds = flow.run_local_server(port=0)
                token_file.parent.mkdir(parents=True, exist_ok=True)
                try:
                    token_file.parent.chmod(0o700)
                except Exception:
                    pass
                with open(token_file, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
                try:
                    token_file.chmod(0o600)
                except Exception:
                    pass
            return creds
        except Exception as e:
            logger.warning(f"Gmail initialize falhou: {type(e).__name__}")
            return None

    def initialize(self) -> bool:
        return True

    def get_tools(self) -> list:
        return [
            self.list_messages,
            self.get_message,
            self.send_message,
            self.reply_message,
            self.modify_labels,
            self.search_messages,
            self.list_labels,
        ]

    @tool(description="Lista e-mails com filtros")
    async def list_messages(
        self,
        query: str | None = None,
        max_results: int = 20,
        label_ids: list[str] | None = None,
        include_spam_trash: bool = False,
        user_id: str | None = None,
    ) -> list[dict]:
        """Lista e-mails. Query usa sintaxe Gmail (ex: 'from:joao is:unread').
        
        CIPHER-001 FIX: Usa token OAuth2 específico do user_id para isolamento multi-tenant.
        """
        _uid = user_id or "system"
        
        creds = self._get_credentials_for_user(user_id)
        if not creds:
            return [{"error": f"OAuth token não encontrado para user_id={_uid}"}]
        
        from googleapiclient.discovery import build
        try:
            params = {
                "userId": "me",
                "maxResults": max_results,
                "includeSpamTrash": include_spam_trash,
            }
            if query:
                params["q"] = query
            if label_ids:
                params["labelIds"] = label_ids

            service = build("gmail", "v1", credentials=creds)
            result = service.users().messages().list(**params).execute()
            messages = result.get("messages", [])

            detailed = []
            for msg in messages[:10]:
                detail = service.users().messages().get(
                    userId="me", id=msg["id"], format="metadata"
                ).execute()

                headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}

                detailed.append({
                    "id": msg["id"],
                    "thread_id": msg["threadId"],
                    "subject": headers.get("Subject", "(sem assunto)"),
                    "from": headers.get("From", ""),
                    "to": headers.get("To", ""),
                    "date": headers.get("Date", ""),
                    "snippet": detail.get("snippet", ""),
                    "labels": detail.get("labelIds", []),
                })

            return detailed
        except Exception as e:
            logger.error(f"Erro ao listar e-mails: {e}")
            return [{"error": str(e)}]

    @tool(description="Le e-mail completo por ID")
    async def get_message(self, message_id: str, user_id: str | None = None) -> dict:
        """Le e-mail completo com corpo."""
        _uid = user_id or "system"
        
        creds = self._get_credentials_for_user(user_id)
        if not creds:
            return {"error": f"OAuth token não encontrado para user_id={_uid}"}
        
        from googleapiclient.discovery import build
        try:
            service = build("gmail", "v1", credentials=creds)
            msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()

            payload = msg.get("payload", {})
            headers = {h["name"]: h["value"] for h in payload.get("headers", [])}

            body = self._extract_body(payload)

            return {
                "id": msg["id"],
                "thread_id": msg["threadId"],
                "subject": headers.get("Subject", ""),
                "from": headers.get("From", ""),
                "to": headers.get("To", ""),
                "cc": headers.get("Cc", ""),
                "date": headers.get("Date", ""),
                "body": body,
                "snippet": msg.get("snippet", ""),
                "labels": msg.get("labelIds", []),
            }
        except Exception as e:
            logger.error(f"Erro ao ler e-mail: {e}")
            return {"error": str(e)}

    def _extract_body(self, payload: dict) -> str:
        import base64
        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain":
                    data = part["body"].get("data", "")
                    if data:
                        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                elif part.get("mimeType") == "text/html":
                    data = part["body"].get("data", "")
                    if data:
                        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                elif "parts" in part:
                    result = self._extract_body(part)
                    if result:
                        return result
        else:
            if payload.get("mimeType") in ("text/plain", "text/html"):
                data = payload["body"].get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        return ""

    @tool(description="Envia novo e-mail")
    async def send_message(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        thread_id: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Envia e-mail. Body pode ser HTML."""
        _uid = user_id or "system"
        
        creds = self._get_credentials_for_user(user_id)
        if not creds:
            return {"error": f"OAuth token não encontrado para user_id={_uid}"}
        
        import base64
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from googleapiclient.discovery import build

        message = MIMEMultipart("alternative")
        message["to"] = ", ".join(to) if isinstance(to, list) else to
        message["subject"] = subject
        if cc:
            message["cc"] = ", ".join(cc)
        if bcc:
            message["bcc"] = ", ".join(bcc)

        if "<html" in body.lower() or "<body" in body.lower():
            message.attach(MIMEText(body, "html"))
        else:
            message.attach(MIMEText(body, "plain"))

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        body_dict = {"raw": raw}
        if thread_id:
            body_dict["threadId"] = thread_id

        service = build("gmail", "v1", credentials=creds)
        sent = service.users().messages().send(userId="me", body=body_dict).execute()
        return {
            "id": sent["id"],
            "thread_id": sent["threadId"],
            "message": "E-mail enviado com sucesso",
        }

    @tool(description="Responde a um e-mail existente")
    async def reply_message(self, message_id: str, body: str, reply_all: bool = False, user_id: str | None = None) -> dict:
        """Responde a um e-mail mantendo thread."""
        _uid = user_id or "system"
        
        creds = self._get_credentials_for_user(user_id)
        if not creds:
            return {"error": f"OAuth token não encontrado para user_id={_uid}"}
        
        import base64
        from email.mime.text import MIMEText
        from googleapiclient.discovery import build
        try:
            service = build("gmail", "v1", credentials=creds)
            original = service.users().messages().get(userId="me", id=message_id, format="metadata").execute()
            headers = {h["name"]: h["value"] for h in original.get("payload", {}).get("headers", [])}

            to = headers.get("From", "")
            subject = headers.get("Subject", "")
            if not subject.startswith("Re:"):
                subject = f"Re: {subject}"

            in_reply_to = headers.get("Message-ID", "")
            references = headers.get("References", "")
            if in_reply_to:
                references = f"{references} {in_reply_to}".strip()

            message = MIMEText(body, "plain")
            message["to"] = to
            message["subject"] = subject
            if in_reply_to:
                message["In-Reply-To"] = in_reply_to
            if references:
                message["References"] = references

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

            sent = service.users().messages().send(
                userId="me", body={"raw": raw, "threadId": original["threadId"]}
            ).execute()

            return {"id": sent["id"], "message": "Resposta enviada"}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Modifica labels de um e-mail")
    async def modify_labels(
        self,
        message_id: str,
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Adiciona/remove labels (ex: 'UNREAD', 'STARRED', 'INBOX', 'Label_123')."""
        _uid = user_id or "system"
        
        creds = self._get_credentials_for_user(user_id)
        if not creds:
            return {"error": f"OAuth token não encontrado para user_id={_uid}"}
        
        from googleapiclient.discovery import build
        try:
            service = build("gmail", "v1", credentials=creds)
            body = {}
            if add_labels:
                body["addLabelIds"] = add_labels
            if remove_labels:
                body["removeLabelIds"] = remove_labels

            service.users().messages().modify(userId="me", id=message_id, body=body).execute()
            return {"success": True, "message": "Labels atualizados"}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Busca avancada de e-mails")
    async def search_messages(self, query: str, max_results: int = 20, user_id: str | None = None) -> list[dict]:
        """Busca usando sintaxe Gmail completa."""
        _uid = user_id or "system"
        
        creds = self._get_credentials_for_user(user_id)
        if not creds:
            return [{"error": f"OAuth token não encontrado para user_id={_uid}"}]
        
        return await self.list_messages(query=query, max_results=max_results, user_id=user_id)

    @tool(description="Lista todos os labels disponiveis")
    async def list_labels(self, user_id: str | None = None) -> list[dict]:
        """Lista labels do Gmail."""
        _uid = user_id or "system"
        
        creds = self._get_credentials_for_user(user_id)
        if not creds:
            return [{"error": f"OAuth token não encontrado para user_id={_uid}"}]
        
        from googleapiclient.discovery import build
        try:
            service = build("gmail", "v1", credentials=creds)
            result = service.users().labels().list(userId="me").execute()
            return [{
                "id": l["id"],
                "name": l["name"],
                "type": l.get("type", "user"),
                "messages_total": l.get("messagesTotal", 0),
                "messages_unread": l.get("messagesUnread", 0),
            } for l in result.get("labels", [])]
        except Exception as e:
            return [{"error": str(e)}]

@skill("email", "Gmail integration com OAuth multi-tenant", tags=["email", "gmail"], requires_auth=True)
class _EmailWrapper(EmailSkill):
    pass
