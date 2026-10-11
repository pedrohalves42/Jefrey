"""Skill: E-mail (Gmail) - OAuth multi-tenant (CIPHER-001 fix)."""
from __future__ import annotations
from typing import Final
import logging
from pathlib import Path

from src.jefrey.adapters.outbound.google_credentials import GoogleCredentials
from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool
from src.jefrey.core.config import get_settings

logger = logging.getLogger(__name__)


def _unprotect(v):
    from src.jefrey.core.secret_store import unprotect
    return unprotect(v)


def _protect(v):
    from src.jefrey.core.secret_store import protect
    return protect(v)

def compact_message(msg_id: str, thread_id: str, headers: dict, detail: dict) -> dict:
    """Um e-mail em poucas linhas: o resultado da ferramenta tem limite de tamanho (antes 10 e-mails completos estouravam
    e o modelo recebia JSON cortado, tentava de novo e demorava ~30 s). `unread` responde "quantos nao lidos"."""
    def cut(s: object, n: int) -> str:
        return " ".join(str(s or "").split())[:n]

    return {
        "id": msg_id,
        "thread_id": thread_id,
        "subject": cut(headers.get("Subject", "(sem assunto)"), 90),
        "from": cut(headers.get("From", ""), 60),
        "date": cut(headers.get("Date", ""), 31),
        "snippet": cut(detail.get("snippet", ""), 110),
        "unread": "UNREAD" in (detail.get("labelIds") or []),
    }


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
        self._google = GoogleCredentials("gmail", "gmail", self.SCOPES)
        self._token_cache = self._google.cache  # credenciais por pessoa (CIPHER-001)

    def _get_credentials_for_user(self, user_id: str | None = None):
        """Credenciais OAuth2 desta pessoa (codigo compartilhado em adapters/outbound/google_credentials.py)."""
        return self._google.for_user(user_id)

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
        
        from src.jefrey.adapters.outbound.google_credentials import build_service as build
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

                detailed.append(compact_message(msg["id"], msg.get("threadId", ""), headers, detail))
            total = result.get("resultSizeEstimate")
            if isinstance(total, int) and total > len(detailed):
                detailed.append({"total_estimado": total, "mostrando": len(detailed)})  # para o modelo nao dizer que so existem estes

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
        
        from src.jefrey.adapters.outbound.google_credentials import build_service as build
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
        from src.jefrey.adapters.outbound.google_credentials import build_service as build

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
        from src.jefrey.adapters.outbound.google_credentials import build_service as build
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
        
        from src.jefrey.adapters.outbound.google_credentials import build_service as build
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
        
        from src.jefrey.adapters.outbound.google_credentials import build_service as build
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
