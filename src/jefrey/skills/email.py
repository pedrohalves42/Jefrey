"""Skill: E-mail (Gmail) - Com instrucoes OAuth."""
from __future__ import annotations
from typing import Any
import logging
from pathlib import Path

from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool
from src.jefrey.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailSkill(SkillBase):
    metadata = SkillMetadata(
        name="email",
        description="Gerencia Gmail (ler, enviar, organizar, buscar)",
        tags=["email", "gmail", "communication", "productivity"],
        requires_auth=True,
        enabled_by_default=True,
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
    
    def initialize(self) -> bool:
        """Inicializa OAuth do Gmail (AXIOM+CIPHER least privilege)."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError:
            logger.warning("google-api-python-client nao instalado. Instale: pip install google-api-python-client google-auth-oauthlib")
            try:
                from src.jefrey.core.metrics import SKILL_INIT_TOTAL
                SKILL_INIT_TOTAL.labels(skill="email", status="skip").inc()
            except Exception:
                pass
            return False
        cfg = get_settings().integrations.gmail
        creds_file = Path(cfg.credentials_file)
        token_file = Path(cfg.token_file)
        if not creds_file.exists():
            logger.warning(f"Credenciais Gmail nao encontradas: {creds_file}")
            logger.info("Criar em https://console.cloud.google.com -> APIs & Services -> Library -> Gmail API -> Enable -> Credentials -> OAuth Client ID (Desktop) -> Download JSON -> config/credentials/gmail.json")
            try:
                from src.jefrey.core.metrics import SKILL_INIT_TOTAL
                SKILL_INIT_TOTAL.labels(skill="email", status="skip").inc()
            except Exception:
                pass
            return False
        try:
            if token_file.exists():
                self._creds = Credentials.from_authorized_user_file(str(token_file), self.SCOPES)
            if not self._creds or not self._creds.valid:
                if self._creds and self._creds.expired and self._creds.refresh_token:
                    try:
                        self._creds.refresh(Request())
                        try:
                            from src.jefrey.core.metrics import OAUTH_REFRESH_TOTAL
                            OAUTH_REFRESH_TOTAL.labels(skill="email", status="ok").inc()
                        except Exception:
                            pass
                    except Exception as e:
                        logger.warning(f"Gmail token refresh falhou: {type(e).__name__}")
                        try:
                            from src.jefrey.core.metrics import OAUTH_REFRESH_TOTAL
                            OAUTH_REFRESH_TOTAL.labels(skill="email", status="fail").inc()
                        except Exception:
                            pass
                        return False
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), self.SCOPES)
                    self._creds = flow.run_local_server(port=0)
                token_file.parent.mkdir(parents=True, exist_ok=True)
                try:
                    token_file.parent.chmod(0o700)
                except Exception:
                    pass
                with open(token_file, "w", encoding="utf-8") as f:
                    f.write(self._creds.to_json())
                try:
                    token_file.chmod(0o600)
                except Exception:
                    pass
            self._service = build("gmail", "v1", credentials=self._creds)
            logger.info("Gmail conectado com sucesso")
            try:
                from src.jefrey.core.metrics import SKILL_INIT_TOTAL
                SKILL_INIT_TOTAL.labels(skill="email", status="ok").inc()
            except Exception:
                pass
            return True
        except Exception as e:
            logger.warning(f"Gmail initialize falhou: {type(e).__name__}")
            try:
                from src.jefrey.core.metrics import SKILL_INIT_TOTAL
                SKILL_INIT_TOTAL.labels(skill="email", status="fail").inc()
            except Exception:
                pass
            return False


    def get_tools(self) -> list:
        if not self._service:
            return []
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
    ) -> list[dict]:
        """Lista e-mails. Query usa sintaxe Gmail (ex: 'from:joao is:unread')."""
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
            
            result = self._service.users().messages().list(**params).execute()
            messages = result.get("messages", [])
            
            # Busca detalhes de cada mensagem
            detailed = []
            for msg in messages[:10]:  # Limita para nao estourar quota
                detail = self._service.users().messages().get(
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
    async def get_message(self, message_id: str) -> dict:
        """Le e-mail completo com corpo."""
        try:
            msg = self._service.users().messages().get(userId="me", id=message_id, format="full").execute()
            
            payload = msg.get("payload", {})
            headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
            
            # Extrai corpo
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
        """Extrai corpo do e-mail recursivamente."""
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
    ) -> dict:
        """Envia e-mail. Body pode ser HTML."""
        import base64
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        try:
            message = MIMEMultipart("alternative")
            message["to"] = ", ".join(to) if isinstance(to, list) else to
            message["subject"] = subject
            if cc:
                message["cc"] = ", ".join(cc)
            if bcc:
                message["bcc"] = ", ".join(bcc)
            
            # Detecta se e HTML
            if "<html" in body.lower() or "<body" in body.lower():
                message.attach(MIMEText(body, "html"))
            else:
                message.attach(MIMEText(body, "plain"))
            
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            body_dict = {"raw": raw}
            if thread_id:
                body_dict["threadId"] = thread_id
            
            sent = self._service.users().messages().send(userId="me", body=body_dict).execute()
            return {
                "id": sent["id"],
                "thread_id": sent["threadId"],
                "message": "E-mail enviado com sucesso",
            }
        except Exception as e:
            logger.error(f"Erro ao enviar e-mail: {e}")
            return {"error": str(e)}
    
    @tool(description="Responde a um e-mail existente")
    async def reply_message(self, message_id: str, body: str, reply_all: bool = False) -> dict:
        """Responde a um e-mail mantendo thread."""
        try:
            original = self._service.users().messages().get(userId="me", id=message_id, format="metadata").execute()
            headers = {h["name"]: h["value"] for h in original.get("payload", {}).get("headers", [])}
            
            to = headers.get("From", "")
            subject = headers.get("Subject", "")
            if not subject.startswith("Re:"):
                subject = f"Re: {subject}"
            
            # Headers para threading
            in_reply_to = headers.get("Message-ID", "")
            references = headers.get("References", "")
            if in_reply_to:
                references = f"{references} {in_reply_to}".strip()
            
            import base64
            from email.mime.text import MIMEText
            
            message = MIMEText(body, "plain")
            message["to"] = to
            message["subject"] = subject
            if in_reply_to:
                message["In-Reply-To"] = in_reply_to
            if references:
                message["References"] = references
            
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            sent = self._service.users().messages().send(
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
    ) -> dict:
        """Adiciona/remove labels (ex: 'UNREAD', 'STARRED', 'INBOX', 'Label_123')."""
        try:
            body = {}
            if add_labels:
                body["addLabelIds"] = add_labels
            if remove_labels:
                body["removeLabelIds"] = remove_labels
            
            self._service.users().messages().modify(userId="me", id=message_id, body=body).execute()
            return {"success": True, "message": "Labels atualizados"}
        except Exception as e:
            return {"error": str(e)}
    
    @tool(description="Busca avancada de e-mails")
    async def search_messages(self, query: str, max_results: int = 20) -> list[dict]:
        """Busca usando sintaxe Gmail completa."""
        return await self.list_messages(query=query, max_results=max_results)
    
    @tool(description="Lista todos os labels disponiveis")
    async def list_labels(self) -> list[dict]:
        """Lista labels do Gmail."""
        try:
            result = self._service.users().labels().list(userId="me").execute()
            return [{
                "id": l["id"],
                "name": l["name"],
                "type": l.get("type", "user"),
                "messages_total": l.get("messagesTotal", 0),
                "messages_unread": l.get("messagesUnread", 0),
            } for l in result.get("labels", [])]
        except Exception as e:
            return [{"error": str(e)}]


@skill("email", "Gmail integration com OAuth", tags=["email", "gmail"], requires_auth=True)
class _EmailWrapper(EmailSkill):
    pass