"""Skill: Calendário (Google Calendar) - Com instruções OAuth."""
from __future__ import annotations
from typing import Any
import os
import json
import logging
from pathlib import Path

from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool
from src.jefrey.core.config import get_settings

logger = logging.getLogger(__name__)


class CalendarSkill(SkillBase):
    metadata = SkillMetadata(
        name="calendar",
        description="Gerencia Google Calendar (eventos, disponibilidade, conflitos)",
        tags=["calendar", "schedule", "google", "productivity"],
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
    
    SCOPES = ["https://www.googleapis.com/auth/calendar"]
    
    def __init__(self):
        super().__init__()
        self._service = None
        self._creds = None
    
    def initialize(self) -> bool:
        """Inicializa OAuth do Google Calendar."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError:
            logger.warning("google-api-python-client não instalado. Instale: pip install google-api-python-client google-auth-oauthlib")
            return False
        
        cfg = get_settings().integrations.google_calendar
        creds_file = Path(cfg.credentials_file)
        token_file = Path(cfg.token_file)
        
        if not creds_file.exists():
            logger.warning(f"Credenciais Google Calendar não encontradas: {creds_file}")
            logger.info("""
            ╔══════════════════════════════════════════════════════════════╗
            ║  CONFIGURAÇÃO GOOGLE CALENDAR OAUTH                          ║
            ╠═════════════════════════════════════════════════════════════╣
            ║  1. Acesse: https://console.cloud.google.com/               ║
            ║  2. Crie projeto ou selecione existente                     ║
            ║  3. APIs & Services → Library → "Google Calendar API"      ║
            ║  4. Enable API                                              ║
            ║  5. Credentials → Create Credentials → OAuth Client ID     ║
            ║  6. Application type: Desktop app                           ║
            ║  7. Download JSON → salve como config/credentials/         ║
            ║     google_calendar.json                                    ║
            ║  8. Execute: python -m scripts.setup_google_calendar       ║
            ╚═════════════════════════════════════════════════════════════╝
            """)
            return False
        
        # Carrega credenciais salvas
        if token_file.exists():
            self._creds = Credentials.from_authorized_user_file(str(token_file), self.SCOPES)
        
        # Refresh ou novo flow
        if not self._creds or not self._creds.valid:
            if self._creds and self._creds.expired and self._creds.refresh_token:
                self._creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), self.SCOPES)
                self._creds = flow.run_local_server(port=0)
            
            # Salva token
            token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(token_file, "w") as f:
                f.write(self._creds.to_json())
        
        self._service = build("calendar", "v3", credentials=self._creds)
        logger.info("Google Calendar conectado com sucesso")
        return True
    
    def get_tools(self) -> list:
        if not self._service:
            return []
        return [
            self.list_events,
            self.create_event,
            self.update_event,
            self.delete_event,
            self.find_free_slots,
            self.get_calendar_list,
        ]
    
    @tool(description="Lista eventos do calendário em um período")
    async def list_events(
        self,
        time_min: str | None = None,
        time_max: str | None = None,
        query: str | None = None,
        max_results: int = 20,
        calendar_id: str = "primary",
    ) -> list[dict]:
        """Lista eventos. time_min/time_max em ISO 8601 (ex: 2024-01-15T09:00:00-03:00)."""
        from datetime import datetime, timezone
        
        if not time_min:
            time_min = datetime.now(timezone.utc).isoformat()
        
        try:
            events_result = self._service.events().list(
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
                "summary": e.get("summary", "(sem título)"),
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
    
    @tool(description="Cria novo evento no calendário")
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
    ) -> dict:
        """Cria evento. Datetimes em ISO 8601 com timezone."""
        from datetime import datetime
        
        if not end_datetime:
            # Default 1 hora
            start = datetime.fromisoformat(start_datetime.replace("Z", "+00:00"))
            from datetime import timedelta
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
            created = self._service.events().insert(calendarId=calendar_id, body=event).execute()
            return {
                "id": created["id"],
                "summary": created["summary"],
                "start": created["start"],
                "end": created["end"],
                "html_link": created.get("htmlLink"),
                "message": "✅ Evento criado com sucesso",
            }
        except Exception as e:
            logger.error(f"Erro ao criar evento: {e}")
            return {"error": str(e)}
    
    @tool(description="Atualiza evento existente")
    async def update_event(self, event_id: str, calendar_id: str = "primary", **updates) -> dict:
        """Atualiza evento. Campos: summary, start_datetime, end_datetime, description, location, attendees."""
        try:
            # Pega evento atual
            event = self._service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            
            # Aplica updates
            if "summary" in updates:
                event["summary"] = updates["summary"]
            if "description" in updates:
                event["description"] = updates["description"]
            if "location" in updates:
                event["location"] = updates["location"]
            if "start_datetime" in updates:
                event["start"]["dateTime"] = updates["start_datetime"]
            if "end_datetime" in updates:
                event["end"]["dateTime"] = updates["end_datetime"]
            if "attendees" in updates:
                event["attendees"] = [{"email": a} for a in updates["attendees"]]
            
            updated = self._service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
            return {"id": updated["id"], "message": "✅ Evento atualizado"}
        except Exception as e:
            return {"error": str(e)}
    
    @tool(description="Remove evento do calendário")
    async def delete_event(self, event_id: str, calendar_id: str = "primary") -> dict:
        """Remove evento."""
        try:
            self._service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            return {"success": True, "message": "✅ Evento removido"}
        except Exception as e:
            return {"error": str(e)}
    
    @tool(description="Encontra horários livres em um período")
    async def find_free_slots(
        self,
        time_min: str,
        time_max: str,
        duration_minutes: int = 60,
        calendar_id: str = "primary",
    ) -> list[dict]:
        """Encontra slots livres. Retorna lista de {start, end}."""
        from datetime import datetime, timedelta
        
        try:
            # Busca eventos ocupados
            events_result = self._service.events().list(
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
            
            # Calcula slots livres (simplificado)
            # Em produção, use freebusy API
            return [{
                "message": f"Use freebusy API para cálculo preciso. {len(busy)} eventos ocupados no período.",
                "busy_count": len(busy),
            }]
        except Exception as e:
            return [{"error": str(e)}]
    
    @tool(description="Lista calendários disponíveis")
    async def get_calendar_list(self) -> list[dict]:
        """Lista calendários do usuário."""
        try:
            result = self._service.calendarList().list().execute()
            return [{
                "id": c["id"],
                "summary": c["summary"],
                "primary": c.get("primary", False),
                "access_role": c.get("accessRole"),
            } for c in result.get("items", [])]
        except Exception as e:
            return [{"error": str(e)}]


@skill("calendar", "Google Calendar integration com OAuth", tags=["calendar", "google"], requires_auth=True)
class _CalendarWrapper(CalendarSkill):
    pass