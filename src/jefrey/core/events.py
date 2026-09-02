"""Sistema de Eventos Assíncrono para Hooks e Extensibilidade."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Awaitable
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Event:
    name: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "system"
    correlation_id: str = ""


EventHandler = Callable[[Event], Awaitable[None] | None]


class EventBus:
    """Bus de eventos assíncrono.

    Usa referências fortes (listas) para handlers e wildcards — deliberadamente, para
    que handlers registrados não sejam coletados pelo GC antes de disparar (ver BUG-5:
    **Nenhum weakref é usado** (resolução do BUG‑5: handlers são mantidos em lista normal).
    """
    
    __slots__ = ("_handlers", "_wildcard_handlers", "_lock")
    
    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._wildcard_handlers: list[EventHandler] = []
        self._lock = asyncio.Lock()
    
    def on(self, event_name: str, handler: EventHandler) -> None:
        """Registra handler para evento específico."""
        self._handlers[event_name].append(handler)
        logger.debug(f"Handler registrado para '{event_name}': {getattr(handler, '__qualname__', str(handler))}")
    
    def on_any(self, handler: EventHandler) -> None:
        """Registra handler para todos os eventos."""
        self._wildcard_handlers.append(handler)
    
    def off(self, event_name: str, handler: EventHandler) -> bool:
        """Remove handler."""
        handlers = self._handlers.get(event_name, [])
        for i, h in enumerate(handlers):
            if h is handler:
                handlers.pop(i)
                return True
        return False
    
    async def emit(self, event: Event) -> None:
        """Emite evento para todos os handlers válidos."""
        # Handlers específicos
        await self._emit_to_handlers(event, self._handlers.get(event.name, []))
        
        # Wildcard handlers
        await self._emit_to_handlers(event, self._wildcard_handlers)
    
    async def _emit_to_handlers(self, event: Event, handlers: list[EventHandler]) -> None:
        for handler in list(handlers):
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                handler_name = getattr(handler, '__qualname__', str(handler))
                logger.error(f"Erro no handler {handler_name} para '{event.name}': {e}", exc_info=True)
    
    async def emit_sync(self, name: str, data: dict[str, Any] | None = None, source: str = "system", correlation_id: str = "") -> None:
        """Emite evento de forma conveniente."""
        await self.emit(Event(name=name, data=data or {}, source=source, correlation_id=correlation_id))


# Instância global
event_bus = EventBus()


# Eventos padrão do sistema - Organizados por domínio
class SystemEvents:
    # Ciclo de vida da aplicação
    STARTUP = "system.startup"
    SHUTDOWN = "system.shutdown"
    ERROR = "system.error"
    CONFIG_RELOADED = "system.config_reloaded"
    
    # Conversa
    USER_MESSAGE = "conversation.user_message"
    ASSISTANT_RESPONSE = "conversation.assistant_response"
    ASSISTANT_STREAMING = "conversation.assistant_streaming"
    TOOL_CALL = "conversation.tool_call"
    TOOL_RESULT = "conversation.tool_result"
    CONVERSATION_CLEARED = "conversation.cleared"
    
    # Memória
    MEMORY_SAVED = "memory.saved"
    MEMORY_RETRIEVED = "memory.retrieved"
    MEMORY_DELETED = "memory.deleted"
    
    # Skills
    SKILL_INVOKED = "skill.invoked"
    SKILL_COMPLETED = "skill.completed"
    SKILL_ERROR = "skill.error"
    SKILL_REGISTERED = "skill.registered"
    SKILL_UNREGISTERED = "skill.unregistered"
    
    # Voice
    WAKE_WORD_DETECTED = "voice.wake_word_detected"
    SPEECH_STARTED = "voice.speech_started"
    SPEECH_ENDED = "voice.speech_ended"
    STT_STARTED = "voice.stt_started"
    STT_COMPLETED = "voice.stt_completed"
    TTS_STARTED = "voice.tts_started"
    TTS_COMPLETED = "voice.tts_completed"
    
    # Integrações
    INTEGRATION_AUTH_REQUIRED = "integration.auth_required"
    INTEGRATION_CONNECTED = "integration.connected"
    INTEGRATION_DISCONNECTED = "integration.disconnected"
    INTEGRATION_ERROR = "integration.error"


# Decorator para handlers automáticos
def event_handler(event_name: str):
    """Decorator para registrar handler automaticamente."""
    def decorator(func: EventHandler) -> EventHandler:
        event_bus.on(event_name, func)
        return func
    return decorator


def wildcard_handler(func: EventHandler) -> EventHandler:
    """Decorator para registrar handler para todos os eventos."""
    event_bus.on_any(func)
    return func