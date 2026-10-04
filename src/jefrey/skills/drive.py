"""Skill: Google Drive (drive.file scope) - OAuth multi-tenant (CIPHER-001 fix)."""
from __future__ import annotations
from typing import Final, TypedDict
import logging
from pathlib import Path

from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool
from src.jefrey.core.config import get_settings

logger = logging.getLogger(__name__)

SCOPES: Final[list[str]] = ["https://www.googleapis.com/auth/drive.file"]

class DriveFile(TypedDict, total=False):
    id: str
    name: str
    mimeType: str
    createdTime: str
    modifiedTime: str
    size: int
    mimeType: str
    webViewLink: str
    iconLink: str

class DriveSkill(SkillBase):
    metadata = SkillMetadata(
        name="drive",
        description="Acesso de leitura/gravação ao Google Drive (drive.file scope - menos privilegiado) - OAuth multi-tenant com isolamento por user_id",
        tags=["drive", "storage", "files", "google"],
        requires_auth=True,
        enabled_by_default=True,  # Reabilitado após implementação multi-tenant
    )

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
        
        try:
            from src.jefrey.core.db import get_db
            from src.jefrey.core.models import OAuthToken
            from google.oauth2.credentials import Credentials
            
            with get_db() as session:
                token_record = session.query(OAuthToken).filter(
                    OAuthToken.user_id == user_id,
                    OAuthToken.provider == "google_drive"
                ).first()
                
                if not token_record:
                    logger.warning("CIPHER-001: No OAuth token found for user_id=%s provider=google - usando fallback", user_id)
                    return self._get_fallback_credentials()
                
                creds = Credentials(
                    token=token_record.access_token,
                    refresh_token=token_record.refresh_token,
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
                        token_record.access_token = creds.token
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
        try:
            from src.jefrey.core.config import get_settings
            return get_settings().integrations.google_drive.client_id
        except Exception:
            import os
            return os.getenv("JEFREY_OAUTH__CLIENT_ID", "")
    
    def _get_client_secret(self):
        try:
            from src.jefrey.core.config import get_settings
            return get_settings().integrations.google_drive.client_secret
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
        cfg = get_settings().integrations.google_drive
        creds_file = Path(cfg.credentials_file)
        token_file = Path(cfg.token_file)
        if not creds_file.exists():
            logger.warning(f"Credenciais Google Drive nao encontradas: {creds_file}")
            return None
        try:
            if token_file.exists():
                creds = Credentials.from_authorized_user_file(str(token_file), self.SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                    except Exception as e:
                        logger.warning(f"Drive token refresh falhou: {type(e).__name__}")
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
            logger.warning(f"Drive initialize falhou: {type(e).__name__}")
            return None

    def initialize(self) -> bool:
        return True

    def get_tools(self) -> list:
        return [
            self.list_files,
            self.upload_file,
            self.download_file,
            self.delete_file,
            self.search_files,
            self.get_file_metadata,
        ]

    @tool(description="Lista arquivos no Google Drive")
    async def list_files(
        self,
        query: str | None = None,
        page_token: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Lista arquivos. query pode filtrar por nome, tipo, proprietário.
        
        CIPHER-001 FIX: Usa token OAuth2 específico do user_id para isolamento multi-tenant.
        """
        _uid = user_id or "system"
        
        creds = self._get_credentials_for_user(user_id)
        if not creds:
            return {"files": [], "error": f"OAuth token não encontrado para user_id={_uid}"}
        
        from googleapiclient.discovery import build
        try:
            results: list[DriveFile] = []
            page_count = 0
            page_count_max = 10
            service = build("drive", "v3", credentials=creds)
            while True:
                call = service.files().list(
                    q=query,
                    pageToken=page_token,
                    fields="nextPageToken, files(id, name, mimeType, size, webViewLink)",
                    spaces="drive",
                )
                response = call.execute()
                for file in response.get("files", []):
                    results.append(
                        {
                            "id": file.get("id"),
                            "name": file.get("name"),
                            "mimeType": file.get("mimeType"),
                            "size": file.get("size"),
                            "webViewLink": file.get("webViewLink"),
                        }
                    )
                page_token = response.get("nextPageToken")
                page_count += 1
                if not page_token or page_count >= page_count_max:
                    break
            return {"files": results, "nextPageToken": page_token}
        except Exception as e:
            logger.error(f"Erro ao listar arquivos: {e}")
            return {"files": [], "error": str(e)}

    @tool(description="Upload de arquivo para o Google Drive")
    async def upload_file(
        self,
        filename: str,
        data: bytes,
        mime_type: str = "application/octet-stream",
        user_id: str | None = None,
    ) -> dict:
        """Upload de arquivo. filename deve incluir extensao."""
        _uid = user_id or "system"
        
        creds = self._get_credentials_for_user(user_id)
        if not creds:
            return {"error": f"OAuth token não encontrado para user_id={_uid}"}
        
        from googleapiclient.discovery import build
        try:
            service = build("drive", "v3", credentials=creds)
            file_metadata = {"name": filename}
            media = {
                "mimeType": mime_type,
                "body": data,
            }
            file = service.files().create(
                body=file_metadata, media_body=media, fields="id, name, webViewLink"
            ).execute()
            return {
                "id": file.get("id"),
                "name": file.get("name"),
                "webViewLink": file.get("webViewLink"),
                "message": "Arquivo enviado com sucesso",
            }
        except Exception as e:
            logger.error(f"Erro ao fazer upload: {e}")
            return {"error": str(e), "message": "Falha no upload"}

    @tool(description="Download de arquivo do Google Drive")
    async def download_file(
        self,
        file_id: str,
        filename: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Download de arquivo pelo file_id."""
        _uid = user_id or "system"
        
        creds = self._get_credentials_for_user(user_id)
        if not creds:
            return {"error": f"OAuth token não encontrado para user_id={_uid}"}
        
        from googleapiclient.discovery import build
        try:
            service = build("drive", "v3", credentials=creds)
            request = service.files().get_media(fileId=file_id)
            file_data = request.execute()
            result: dict = {"file_id": file_id, "data": file_data}
            if filename:
                result["filename"] = filename
            return result
        except Exception as e:
            logger.error(f"Erro ao fazer download: {e}")
            return {"error": str(e), "message": "Falha no download"}

    @tool(description="Remove arquivo do Google Drive")
    async def delete_file(
        self,
        file_id: str,
        user_id: str | None = None,
    ) -> dict:
        """Remove arquivo permanentemente."""
        _uid = user_id or "system"
        
        creds = self._get_credentials_for_user(user_id)
        if not creds:
            return {"error": f"OAuth token não encontrado para user_id={_uid}"}
        
        from googleapiclient.discovery import build
        try:
            service = build("drive", "v3", credentials=creds)
            service.files().delete(fileId=file_id).execute()
            return {"success": True, "message": "Arquivo removido"}
        except Exception as e:
            logger.error(f"Erro ao remover arquivo: {e}")
            return {"error": str(e), "message": "Falha ao remover"}

    @tool(description="Busca arquivos no Google Drive por nome ou conteúdo")
    async def search_files(
        self,
        query: str,
        user_id: str | None = None,
    ) -> dict:
        """Busca por nome ou conteúdo do arquivo."""
        _uid = user_id or "system"
        
        creds = self._get_credentials_for_user(user_id)
        if not creds:
            return {"files": [], "error": f"OAuth token não encontrado para user_id={_uid}"}
        
        from googleapiclient.discovery import build
        try:
            service = build("drive", "v3", credentials=creds)
            results: list[DriveFile] = []
            page_token = None
            while True:
                call = service.files().list(
                    q=query,
                    pageToken=page_token,
                    fields="nextPageToken, files(id, name, mimeType, size, webViewLink)",
                    spaces="drive",
                )
                response = call.execute()
                for file in response.get("files", []):
                    results.append(
                        {
                            "id": file.get("id"),
                            "name": file.get("name"),
                            "mimeType": file.get("mimeType"),
                            "size": file.get("size"),
                            "webViewLink": file.get("webViewLink"),
                        }
                    )
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
            return {"files": results}
        except Exception as e:
            logger.error(f"Erro ao buscar arquivos: {e}")
            return {"files": [], "error": str(e)}

    @tool(description="Retorna metadados completos de um arquivo")
    async def get_file_metadata(
        self,
        file_id: str,
        user_id: str | None = None,
    ) -> dict:
        """Retorna metadados completos de um arquivo pelo file_id."""
        _uid = user_id or "system"
        
        creds = self._get_credentials_for_user(user_id)
        if not creds:
            return {"error": f"OAuth token não encontrado para user_id={_uid}"}
        
        from googleapiclient.discovery import build
        try:
            service = build("drive", "v3", credentials=creds)
            file = service.files().get(fileId=file_id).execute()
            return {
                "id": file.get("id"),
                "name": file.get("name"),
                "mimeType": file.get("mimeType"),
                "createdTime": file.get("createdTime"),
                "modifiedTime": file.get("modifiedTime"),
                "size": file.get("size"),
                "webViewLink": file.get("webViewLink"),
                "owners": file.get("owners"),
                "shared": file.get("shared"),
                "parents": file.get("parents"),
            }
        except Exception as e:
            logger.error(f"Erro ao obter metadados: {e}")
            return {"error": str(e)}

@skill("drive", "Google Drive integration com OAuth multi-tenant (drive.file scope)", tags=["drive", "storage"], requires_auth=True)
class _DriveWrapper(DriveSkill):
    pass
