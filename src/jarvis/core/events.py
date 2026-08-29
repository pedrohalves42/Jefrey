"""Sistema de Eventos para hooks e extensibilidade."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Awaitable
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class Event:
    name: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "system"


EventHandler = Callable[[Event], Awaitable[None] | None]


class EventBus:
    """Bus de eventos assíncrono para desacoplamento."""
    
    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._wildcard_handlers: list[EventHandler] = []
    
    def on(self, event_name: str, handler: EventHandler) -> None:
        """Registra handler para evento específico."""
        self._handlers[event_name].append(handler)
        logger.debug(f"Handler registrado para '{event_name}': {handler.__name__}")
    
    def on_any(self, handler: EventHandler) -> None:
        """Registra handler para todos os eventos."""
        self._wildcard_handlers.append(handler)
    
    def off(self, event_name: str, handler: EventHandler) -> bool:
        """Remove handler."""
        if handler in self._handlers.get(event_name, []):
            self._handlers[event_name].remove(handler)
            return True
        return False
    
    async def emit(self, event: Event) -> None:
        """Emite evento para todos os handlers."""
        # Handlers específicos
        for handler in self._handlers.get(event.name, []):
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Erro no handler {handler.__name__} para '{event.name}': {e}")
        
        # Wildcard handlers
        for handler in self._wildcard_handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Erro no wildcard handler {handler.__name__}: {e}")
    
    async def emit_sync(self, name: str, data: dict[str, Any] | None = None, source: str = "system") -> None:
        """Emite evento de forma síncrona (convenience)."""
        await self.emit(Event(name=name, data=data or {}, source=source))


# Instância global
event_bus = EventBus()


# Eventos padrão do sistema
class SystemEvents:
    # Ciclo de vida
    STARTUP = "system.startup"
    SHUTDOWN = "system.shutdown"
    ERROR = "system.error"
    
    # Conversa
    USER_MESSAGE = "conversation.user_message"
    ASSISTANT_RESPONSE = "conversation.assistant_response"
    TOOL_CALL = "conversation.tool_call"
    TOOL_RESULT = "conversation.tool_result"
    
    # Memória
    MEMORY_SAVED = "memory.saved"
    MEMORY_RETRIEVED = "memory.retrieved"
    
    # Skills
    SKILL_INVOKED = "skill.invoked"
    SKILL_COMPLETED = "skill.completed"
    SKILL_ERROR = "skill.error"
    
    # Voice
    WAKE_WORD_DETECTED = "voice.wake_word_detected"
    SPEECH_STARTED = "voice.speech_started"
    SPEECH_ENDED = "voice.speech_ended"
    TTS_STARTED = "voice.tts_started"
    TTS_COMPLETED = "voice.tts_completed"