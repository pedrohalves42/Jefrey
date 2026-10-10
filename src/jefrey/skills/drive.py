"""Skill: Google Drive (drive.file scope) - OAuth multi-tenant (CIPHER-001 fix)."""
from __future__ import annotations
from typing import Final, TypedDict
import logging
from pathlib import Path

from src.jefrey.adapters.outbound.google_credentials import GoogleCredentials
from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool
from src.jefrey.core.config import get_settings

logger = logging.getLogger(__name__)

SCOPES: Final[list[str]] = ["https://www.googleapis.com/auth/drive.file"]


def _unprotect(v):
    from src.jefrey.core.secret_store import unprotect
    return unprotect(v)


def _protect(v):
    from src.jefrey.core.secret_store import protect
    return protect(v)

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
        self._google = GoogleCredentials("google_drive", "google_drive", SCOPES)
        self._token_cache = self._google.cache  # credenciais por pessoa (CIPHER-001)

    def _get_credentials_for_user(self, user_id: str | None = None):
        """Credenciais OAuth2 desta pessoa (codigo compartilhado em adapters/outbound/google_credentials.py)."""
        return self._google.for_user(user_id)

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
