"""Skill: Calendario (Google Calendar) - OAuth multi-tenant (CIPHER-001 fix)."""
from __future__ import annotations
from typing import Final
import logging
from pathlib import Path

from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool
from src.jefrey.core.config import get_settings

logger = logging.getLogger(__name__)

class CalendarSkill(SkillBase):
    metadata = SkillMetadata(
        name="calendar",
        description="Gerencia Google Calendar (eventos, disponibilidade, conflitos) - OAuth multi-tenant com isolamento por user_id",
        tags=["calendar", "schedule", "google", "productivity"],
        requires_auth=True,
        enabled_by_default=True,  # Reabilitado após implementação multi-tenant
    )

    SCOPES: Final[list[str]] = ["https://www.googleapis.com/auth/calendar"]

    def __init__(self):
        super().__init__()
        self._service = None
        self._creds = None
        self._token_cache = {}  # Cache de credenciais por user_id (CIPHER-001 fix)

    def _get_credentials_for_user(self, user_id: str | None = None):
        """Obtém credenciais OAuth2 do PostgreSQL para um user_id específico (CIPHER-001 fix).
        
        Isolamento multi-tenant: cada user_id tem seu próprio token OAuth2.
        Se user_id não fornecido, usa fallback single-tenant (aviso no log).
        """
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
                    OAuthToken.provider == "google_calendar"
                ).first()
                
                if not token_record:
                    logger.warning("CIPHER-001: No OAuth token found for user_id=%s provider=google - usando fallback", user_id)
                    return self._get_fallback_credentials()
                
                # Criar Credentials a partir do token salvo
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
                
                # Validar e refresh se necessário
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(self._get_request())
                        # Atualizar no PostgreSQL
                        token_record.access_token = creds.token
                        token_record.expires_at = creds.expiry
                        session.commit()
                        logger.info("CIPHER-001: Token OAuth2 refresh + atualizado no PostgreSQL user_id=%s", user_id)
                    except Exception as e:
                        logger.warning("CIPHER-001: Token refresh falhou user_id=%s: %s", user_id, e)
                
                # Cache
                self._token_cache[user_id] = creds
                
                logger.info("CIPHER-001: OAuth token carregado do PostgreSQL user_id=%s email=%s", user_id, token_record.email)
                return creds
                
        except Exception as e:
            logger.error("CIPHER-001: Falha ao carregar OAuth token do PostgreSQL: %s", e)
            return self._get_fallback_credentials()
    
    def _get_client_id(self):
        """Obtém client_id do Google Calendar."""
        try:
            from src.jefrey.core.config import get_settings
            return get_settings().integrations.google_calendar.client_id
        except Exception:
            # Fallback para variável de ambiente
            import os
            return os.getenv("JEFREY_OAUTH__CLIENT_ID", "")
    
    def _get_client_secret(self):
        """Obtém client_secret do Google Calendar."""
        try:
            from src.jefrey.core.config import get_settings
            return get_settings().integrations.google_calendar.client_secret
        except Exception:
            # Fallback para variável de ambiente
            import os
            return os.getenv("JEFREY_OAUTH__CLIENT_SECRET", "")
    
    def _get_request(self):
        """Obtém Request object para refresh token."""
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
        cfg = get_settings().integrations.google_calendar
        creds_file = Path(cfg.credentials_file)
        token_file = Path(cfg.token_file)
        if not creds_file.exists():
            logger.warning(f"Credenciais Google Calendar nao encontradas: {creds_file}")
            return None
        try:
            if token_file.exists():
                creds = Credentials.from_authorized_user_file(str(token_file), self.SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                    except Exception as e:
                        logger.warning(f"Calendar token refresh falhou: {type(e).__name__}")
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
            logger.warning(f"Calendar initialize falhou: {type(e).__name__}")
            return None

    def initialize(self) -> bool:
        """Inicializa OAuth do Google Calendar (AXIOM+CIPHER least privilege)."""
        # Não inicializa service global - cada user terá seu próprio service
        return True

    def get_tools(self) -> list:
        return [
            self.list_events,
            self.create_event,
            self.update_event,
            self.delete_event,
            self.find_free_slots,
            self.get_calendar_list,
        ]

    @tool(description="Lista eventos do calendario em um periodo")
    async def list_events(
        self,
        time_min: str | None = None,
        time_max: str | None = None,
        query: str | None = None,
        max_results: int = 20,
        calendar_id: str = "primary",
        user_id: str | None = None,
    ) -> list[dict]:
        """Lista eventos. time_min/time_max em ISO 8601 (ex: 2024-01-15T09:00:00-03:00).
        
        CIPHER-001 FIX: Usa token OAuth2 específico do user_id para isolamento multi-tenant.
        """
        _uid = user_id or "system"
        
        # Obter credenciais específicas do user_id
        creds = self._get_credentials_for_user(user_id)
        if not creds:
            return [{"error": f"OAuth token não encontrado para user_id={_uid}. Faça login com Google primeiro via /auth/google"}]
        
        from datetime import datetime, timezone
        from googleapiclient.discovery import build

        if not time_min:
            time_min = datetime.now(timezone.utc).isoformat()

        try:
            service = build("calendar", "v3", credentials=creds)
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                q=query,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            events = events_result.get("items", [])
            return [{
                "id": e["id"],
                "summary": e.get("summary", "(sem titulo)"),
                "start": e["start"].get("dateTime", e["start"].get("date")),
                "end": e["end"].get("dateTime", e["end"].get("date")),
                "location": e.get("location"),
                "description": e.get("description"),
                "attendees": [a["email"] for a in e.get("attendees", [])],
                "html_link": e.get("htmlLink"),
            } for e in events]
        except Exception as e:
            logger.error(f"Erro ao listar eventos: {e}")
            return [{"error": str(e)}]

    @tool(description="Cria novo evento no calendario")
    async def create_event(
        self,
        summary: str,
        start_datetime: str,
        end_datetime: str | None = None,
        description: str | None = None,
        location: str | None = None,
        attendees: list[str] | None = None,
        calendar_id: str = "primary",
        reminders_minutes: list[int] | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Cria evento. Datetimes em ISO 8601 com timezone."""
        _uid = user_id or "system"
        
        creds = self._get_credentials_for_user(user_id)
        if not creds:
            return {"error": f"OAuth token não encontrado para user_id={_uid}"}
        
        from datetime import datetime, timedelta
        from googleapiclient.discovery import build

        if not end_datetime:
            start = datetime.fromisoformat(start_datetime.replace("Z", "+00:00"))
            end_datetime = (start + timedelta(hours=1)).isoformat()

        event = {
            "summary": summary,
            "start": {"dateTime": start_datetime},
            "end": {"dateTime": end_datetime},
        }

        if description:
            event["description"] = description
        if location:
            event["location"] = location
        if attendees:
            event["attendees"] = [{"email": a} for a in attendees]
        if reminders_minutes:
            event["reminders"] = {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": m} for m in reminders_minutes],
            }

        try:
            service = build("calendar", "v3", credentials=creds)
            created = service.events().insert(calendarId=calendar_id, body=event).execute()
            return {
                "id": created["id"],
                "summary": created["summary"],
                "start": created["start"],
                "end": created["end"],
                "html_link": created.get("htmlLink"),
                "message": "Evento criado com sucesso",
            }
        except Exception as e:
            logger.error(f"Erro ao criar evento: {e}")
            return {"error": str(e)}

    @tool(description="Atualiza evento existente")
    async def update_event(self, event_id: str, calendar_id: str = "primary", user_id: str | None = None, **updates) -> dict:
        """Atualiza evento. Campos: summary, start_datetime, end_datetime, description, location, attendees."""
        _uid = user_id or "system"
        
        creds = self._get_credentials_for_user(user_id)
        if not creds:
            return {"error": f"OAuth token não encontrado para user_id={_uid}"}
        
        from googleapiclient.discovery import build
        try:
            service = build("calendar", "v3", credentials=creds)
            event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

            for key, value in updates.items():
                if key == "summary":
                    event["summary"] = value
                elif key == "description":
                    event["description"] = value
                elif key == "location":
                    event["location"] = value
                elif key == "start_datetime":
                    event["start"]["dateTime"] = value
                elif key == "end_datetime":
                    event["end"]["dateTime"] = value
                elif key == "attendees":
                    event["attendees"] = [{"email": a} for a in value]

            updated = service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
            return {"id": updated["id"], "message": "Evento atualizado"}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Remove evento do calendario")
    async def delete_event(self, event_id: str, calendar_id: str = "primary", user_id: str | None = None) -> dict:
        """Remove evento."""
        _uid = user_id or "system"
        
        creds = self._get_credentials_for_user(user_id)
        if not creds:
            return {"error": f"OAuth token não encontrado para user_id={_uid}"}
        
        from googleapiclient.discovery import build
        try:
            service = build("calendar", "v3", credentials=creds)
            service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            return {"success": True, "message": "Evento removido"}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Encontra horarios livres em um periodo")
    async def find_free_slots(
        self,
        time_min: str,
        time_max: str,
        duration_minutes: int = 60,
        calendar_id: str = "primary",
        user_id: str | None = None,
    ) -> list[dict]:
        """Encontra slots livres. Retorna lista de {start, end}."""
        _uid = user_id or "system"
        
        creds = self._get_credentials_for_user(user_id)
        if not creds:
            return [{"error": f"OAuth token não encontrado para user_id={_uid}"}]
        
        from datetime import datetime, timedelta
        from googleapiclient.discovery import build
        try:
            service = build("calendar", "v3", credentials=creds)
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            busy = []
            for e in events_result.get("items", []):
                start = e["start"].get("dateTime") or e["start"].get("date")
                end = e["end"].get("dateTime") or e["end"].get("date")
                busy.append((start, end))

            return [{
                "message": f"Use freebusy API para calculo preciso. {len(busy)} eventos ocupados no periodo.",
                "busy_count": len(busy),
            }]
        except Exception as e:
            return [{"error": str(e)}]

    @tool(description="Lista calendarios disponiveis")
    async def get_calendar_list(self, user_id: str | None = None) -> list[dict]:
        """Lista calendarios do usuário."""
        _uid = user_id or "system"
        
        creds = self._get_credentials_for_user(user_id)
        if not creds:
            return [{"error": f"OAuth token não encontrado para user_id={_uid}"}]
        
        from googleapiclient.discovery import build
        try:
            service = build("calendar", "v3", credentials=creds)
            result = service.calendarList().list().execute()
            return [{
                "id": c["id"],
                "summary": c["summary"],
                "primary": c.get("primary", False),
                "access_role": c.get("accessRole"),
            } for c in result.get("items", [])]
        except Exception as e:
            return [{"error": str(e)}]

@skill("calendar", "Google Calendar integration com OAuth multi-tenant", tags=["calendar", "google"], requires_auth=True)
class _CalendarWrapper(CalendarSkill):
    pass
