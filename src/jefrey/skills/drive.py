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
    size: str
    modifiedTime: str
    webViewLink: str

class DriveSkill(SkillBase):
    metadata = SkillMetadata(
        name="drive",
        description="Gerencia Google Drive com escopo minimo drive.file (apenas arquivos criados pelo app)",
        tags=["drive", "google", "files", "productivity"],
        requires_auth=True,
        enabled_by_default=True,
        config_schema={
            "type": "object",
            "properties": {
                "credentials_file": {"type": "string", "description": "Caminho do client_secret.json"},
                "token_file": {"type": "string", "description": "Caminho do token salvo"},
                "scopes": {"type": "array", "items": {"type": "string"}},
            },
        },
    )

    SCOPES: Final[list[str]] = SCOPES

    def __init__(self) -> None:
        super().__init__()
        self._service = None
        self._creds = None

    def initialize(self) -> bool:
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
            logger.info("Criar em https://console.cloud.google.com -> APIs & Services -> Library -> Google Drive API -> Enable -> Credentials -> OAuth Client ID (Desktop) -> Download JSON -> config/credentials/google_drive.json")
            try:
                from src.jefrey.core.metrics import SKILL_INIT_TOTAL
                SKILL_INIT_TOTAL.labels(skill="drive", status="skip").inc()
            except Exception:
                pass
            return False
        try:
            if token_file.exists():
                self._creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
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
                        logger.warning(f"Drive token refresh falhou: {e}")
                        try:
                            from src.jefrey.core.metrics import OAUTH_REFRESH_TOTAL
                            OAUTH_REFRESH_TOTAL.labels(skill="drive", status="fail").inc()
                        except Exception:
                            pass
                        return False
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
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
            logger.info("Google Drive conectado com sucesso (drive.file)")
            try:
                from src.jefrey.core.metrics import SKILL_INIT_TOTAL
                SKILL_INIT_TOTAL.labels(skill="drive", status="ok").inc()
            except Exception:
                pass
            return True
        except Exception as e:
            logger.warning(f"Drive initialize falhou: {e}")
            try:
                from src.jefrey.core.metrics import SKILL_INIT_TOTAL
                SKILL_INIT_TOTAL.labels(skill="drive", status="fail").inc()
            except Exception:
                pass
            return False

    def get_tools(self) -> list:
        if not self._service:
            return []
        return [self.drive_list_files, self.drive_read_file, self.drive_create_file]

    @tool(description="Lista arquivos do Drive (escopo drive.file - apenas arquivos do app)")
    async def drive_list_files(self, query: str | None = None, page_size: int = 20) -> list[dict]:
        try:
            params: dict[str, Any] = {"pageSize": page_size, "fields": "files(id, name, mimeType, size, modifiedTime, webViewLink)"}
            if query:
                params["q"] = query
            result = self._service.files().list(**params).execute()
            files = result.get("files", [])
            return [{"id": f["id"], "name": f.get("name"), "mimeType": f.get("mimeType"), "size": f.get("size"), "modifiedTime": f.get("modifiedTime"), "webViewLink": f.get("webViewLink")} for f in files]
        except Exception as e:
            logger.error(f"drive_list_files erro: {e}")
            return [{"error": str(e)}]

    @tool(description="Le conteudo de arquivo do Drive por ID")
    async def drive_read_file(self, file_id: str) -> dict:
        try:
            import io
            from googleapiclient.http import MediaIoBaseDownload
            request = self._service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            content = fh.getvalue().decode("utf-8", errors="replace")
            meta = self._service.files().get(fileId=file_id, fields="id, name, mimeType, size").execute()
            return {"id": meta["id"], "name": meta.get("name"), "mimeType": meta.get("mimeType"), "content": content[:20000]}
        except Exception as e:
            logger.error(f"drive_read_file erro: {e}")
            return {"error": str(e)}

    @tool(description="Cria arquivo no Drive (escopo drive.file)")
    async def drive_create_file(self, name: str, content: str, mime_type: str = "text/plain") -> dict:
        try:
            import io
            from googleapiclient.http import MediaIoBaseUpload
            media = MediaIoBaseUpload(io.BytesIO(content.encode("utf-8")), mimetype=mime_type)
            file_metadata: dict[str, Any] = {"name": name}
            created = self._service.files().create(body=file_metadata, media_body=media, fields="id, name, mimeType, webViewLink").execute()
            return {"id": created["id"], "name": created.get("name"), "mimeType": created.get("mimeType"), "webViewLink": created.get("webViewLink"), "message": "Arquivo criado com sucesso"}
        except Exception as e:
            logger.error(f"drive_create_file erro: {e}")
            return {"error": str(e)}

@skill("drive", "Google Drive drive.file com OAuth", tags=["drive", "google"], requires_auth=True)
class _DriveWrapper(DriveSkill):
    pass
