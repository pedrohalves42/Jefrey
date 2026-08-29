"""Skill: Notas e Conhecimento Pessoal."""
from __future__ import annotations
from typing import Any
import logging

from src.jarvis.skills import SkillBase, SkillMetadata, skill, tool
from src.jarvis.core.memory import MemoryManager

logger = logging.getLogger(__name__)


class NotesSkill(SkillBase):
    metadata = SkillMetadata(
        name="notes",
        description="Gerencia notas e base de conhecimento pessoal (memória de longo prazo)",
        tags=["knowledge", "memory", "personal"],
    )
    
    def __init__(self):
        super().__init__()
        self.memory = MemoryManager()
    
    async def initialize(self) -> bool:
        return True
    
    def get_tools(self) -> list:
        return [
            self.save_note,
            self.search_notes,
            self.list_notes,
            self.get_note,
            self.update_note,
            self.delete_note,
        ]
    
    @tool(description="Salva uma nota na base de conhecimento")
    async def save_note(
        self,
        title: str,
        content: str,
        tags: list[str] | None = None,
        source: str = "user",
        **metadata,
    ) -> dict:
        """Salva nota com busca semântica."""
        tags = tags or []
        meta = {"source": source, **metadata}
        note_id = self.memory.long_term.add(content, metadata=meta)
        return {
            "id": note_id,
            "title": title,
            "saved": True,
            "message": f"Nota salva com ID: {note_id[:8]}...",
        }
    
    @tool(description="Busca notas por similaridade semântica")
    async def search_notes(
        self,
        query: str,
        top_k: int = 5,
        tags: list[str] | None = None,
    ) -> list[dict]:
        """Busca semântica nas notas."""
        filter_meta = {"tags": {"$in": tags}} if tags else None
        results = self.memory.long_term.search(query, top_k=top_k, filter_metadata=filter_meta)
        return results
    
    @tool(description="Lista notas recentes")
    async def list_notes(self, limit: int = 20, tags: list[str] | None = None) -> list[dict]:
        """Lista notas recentes."""
        filter_meta = {"tags": {"$in": tags}} if tags else None
        return self.memory.long_term.list_recent(limit=limit, filter_metadata=filter_meta)
    
    @tool(description="Recupera nota por ID")
    async def get_note(self, note_id: str) -> dict | None:
        """Recupera nota específica."""
        return self.memory.long_term.get(note_id)
    
    @tool(description="Atualiza nota existente")
    async def update_note(
        self,
        note_id: str,
        content: str | None = None,
        tags: list[str] | None = None,
        **metadata,
    ) -> dict:
        """Atualiza nota."""
        meta = {}
        if tags is not None:
            meta["tags"] = tags
        meta.update(metadata)
        
        success = self.memory.long_term.update(note_id, content=content, metadata=meta)
        return {"success": success, "id": note_id}
    
    @tool(description="Remove nota")
    async def delete_note(self, note_id: str) -> dict:
        """Remove nota."""
        success = self.memory.long_term.delete(note_id)
        return {"success": success, "id": note_id}


# Auto-registro via decorator
@skill("notes", "Gerencia notas e conhecimento pessoal", tags=["knowledge", "memory"])
class _NotesSkillWrapper(NotesSkill):
    pass