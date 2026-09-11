"""Skill: Google Drive (drive.file scope) - AXIOM+CIPHER least privilege."""
from __future__ import annotations
from typing import Final, TypedDict, Any
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
        description="Acesso de leitura/gravação ao Google Drive (drive.file scope - menos privilegiado)",
        tags=["drive", "storage", "files", "google"],
        requires_auth=True,
        enabled_by_default=True,
    )

    SCOPES: Final[list[str]] = ["https://www.googleapis.com/auth/drive.file"]

    def __init__(self):
        super().__init__()
        self._service = None
        self._creds = None

    def initialize(self) -> bool:
        """Inicializa OAuth do Google Drive (AXIOM+CIPHER least privilege)."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError:
            logger.warning("google-api-python-client nao instalado. Instale: pip install google-api-python-client google-auth-oauthlib")
            try:
                from src.jefrey.core.metrics import SKILL_INIT_TOTAL
                SKILL_INIT_TOTAL.labels(skill="drive", status="skip").inc()
            except Exception:
                pass
            return False
        cfg = get_settings().integrations.google_drive
        creds_file = Path(cfg.credentials_file)
        token_file = Path(cfg.token_file)
        if not creds_file.exists():
            logger.warning(f"Credenciais Google Drive nao encontradas: {creds_file}")
            logger.info(
                "Criar em https://console.cloud.google.com -> APIs & Services -> Library -> Google Drive API -> Enable -> Credentials -> OAuth Client ID (Desktop) -> Download JSON -> config/credentials/google_drive.json"
            )
            try:
                from src.jefrey.core.metrics import SKILL_INIT_TOTAL
                SKILL_INIT_TOTAL.labels(skill="drive", status="skip").inc()
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
                            OAUTH_REFRESH_TOTAL.labels(skill="drive", status="ok").inc()
                        except Exception:
                            pass
                    except Exception as e:
                        logger.warning(f"Drive token refresh falhou: {type(e).__name__}")
                        try:
                            from src.jefrey.core.metrics import OAUTH_REFRESH_TOTAL
                            OAUTH_REFRESH_TOTAL.labels(skill="drive", status="fail").inc()
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
            self._service = build("drive", "v3", credentials=self._creds)
            logger.info("Google Drive conectado com sucesso")
            try:
                from src.jefrey.core.metrics import SKILL_INIT_TOTAL
                SKILL_INIT_TOTAL.labels(skill="drive", status="ok").inc()
            except Exception:
                pass
            return True
        except Exception as e:
            logger.warning(f"Drive initialize falhou: {type(e).__name__}")
            try:
                from src.jefrey.core.metrics import SKILL_INIT_TOTAL
                SKILL_INIT_TOTAL.labels(skill="drive", status="fail").inc()
            except Exception:
                pass
            return False

    def get_tools(self) -> list:
        if not self._service:
            return []
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
        """Lista arquivos. query pode filtrar por nome, tipo, proprietario."""
        _uid = user_id or "system"
        try:
            results: list[DriveFile] = []
            page_count = 0
            page_count_max = 10
            while True:
                call = self._service.files().list(
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
        try:
            file_metadata = {"name": filename}
            media = {
                "mimeType": mime_type,
                "body": data,
            }
            file = self._service.files().create(
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
        try:
            request = self._service.files().get_media(fileId=file_id)
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
        try:
            self._service.files().delete(fileId=file_id).execute()
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
        try:
            results: list[DriveFile] = []
            page_token = None
            while True:
                call = self._service.files().list(
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
        try:
            file = self._service.files().get(fileId=file_id).execute()
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

@skill("drive", "Google Drive integration com OAuth (drive.file scope)", tags=["drive", "storage"], requires_auth=True)
class _DriveWrapper(DriveSkill):
    pass