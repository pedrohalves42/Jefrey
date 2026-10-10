"""Skill: Calendario (Google Calendar) - OAuth multi-tenant (CIPHER-001 fix)."""
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
        self._google = GoogleCredentials("google_calendar", "google_calendar", self.SCOPES)
        self._token_cache = self._google.cache  # credenciais por pessoa (CIPHER-001)

    def _get_credentials_for_user(self, user_id: str | None = None):
        """Credenciais OAuth2 desta pessoa (codigo compartilhado em adapters/outbound/google_credentials.py)."""
        return self._google.for_user(user_id)

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
                "location": (e.get("location") or "")[:100] or None,
                "description": " ".join((e.get("description") or "").split())[:150] or None,  # o resultado da ferramenta tem limite de tamanho
                "attendees": [a.get("email", "") for a in e.get("attendees", [])][:5],
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
