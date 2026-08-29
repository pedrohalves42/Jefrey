"""Core package - Jefrey."""
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

from src.jefrey.core.config import get_settings, reload_settings, AppSettings
from src.jefrey.core.memory import (
    MemoryManager,
    ShortTermMemory,
    LongTermMemory,
    get_memory_manager,
)
from src.jefrey.core.events import event_bus, SystemEvents, event_handler, wildcard_handler
from src.jefrey.core.agent import JefreyAgent, AgentState

__all__ = [
    "get_settings",
    "reload_settings",
    "AppSettings",
    "MemoryManager",
    "ShortTermMemory",
    "LongTermMemory",
    "get_memory_manager",
    "event_bus",
    "SystemEvents",
    "event_handler",
    "wildcard_handler",
    "JefreyAgent",
    "AgentState",
]