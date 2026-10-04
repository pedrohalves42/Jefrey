"""Skill: Notas e Conhecimento Pessoal (Memória de Longo Prazo)."""
from __future__ import annotations
from typing import Any
import logging

from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool
from src.jefrey.core.memory import get_memory_manager

logger = logging.getLogger(__name__)


class NotesSkill(SkillBase):
    metadata = SkillMetadata(
        name="notes",
        description="Gerencia notas e base de conhecimento pessoal com busca semântica",
        tags=["knowledge", "memory", "personal", "productivity"],
        enabled_by_default=True,
    )
    
    def __init__(self):
        super().__init__()
        self.memory = get_memory_manager()
    
    def initialize(self) -> bool:
        # Testa conexão com memória
        try:
            self.memory.long_term.count()
            return True
        except Exception as e:
            logger.error(f"NotesSkill init falhou: {e}")
            return False
    
    def get_tools(self) -> list:
        return [
            self.save_note,
            self.search_notes,
            self.list_notes,
            self.get_note,
            self.update_note,
            self.delete_note,
        ]
    
    @tool(description="Salva uma nota na base de conhecimento com busca semântica")
    async def save_note(
        self,
        title: str,
        content: str,
        tags: list[str] | None = None,
        source: str = "user",
        related_people: list[str] | None = None,
        related_projects: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Salva nota com metadados ricos para busca posterior."""
        tags = tags or []
        metadata = metadata or {}
        meta = {
            "title": title,
            "source": source,
            "tags": tags,
            "related_people": related_people or [],
            "related_projects": related_projects or [],
            **metadata,
        }
        _uid = user_id or "system"
        # o titulo entra no texto indexado: senao "minha cor favorita" nunca acha a nota "Verde-esmeralda"
        indexed = f"{title}\n{content}" if title and title.strip() else content
        note_id = self.memory.long_term.add(indexed, metadata=meta, user_id=_uid)
        logger.info(f"Nota salva: {title} ({note_id[:8]}...)")
        return {
            "id": note_id,
            "title": title,
            "saved": True,
            "message": f"Anotado! Guardei na sua memória: “{(title or content).strip()[:80]}”.",
        }
    
    @tool(description="Busca notas por similaridade semântica (linguagem natural)")
    async def search_notes(
        self,
        query: str,
        top_k: int = 5,
        tags: list[str] | None = None,
        user_id: str | None = None,
    ) -> list[dict]:
        """Busca semântica nas notas. Use linguagem natural."""
        filter_meta = {"tags": {"$in": tags}} if tags else None
        results = self.memory.long_term.search(query, top_k=top_k, filter_metadata=filter_meta, user_id=user_id or "system")
        logger.info(f"Busca notas: '{query}' → {len(results)} resultados")
        return results
    
    @tool(description="Lista notas recentes, opcionalmente filtradas por tags")
    async def list_notes(self, limit: int = 20, tags: list[str] | None = None, user_id: str | None = None) -> list[dict]:
        """Lista notas recentes ordenadas por data."""
        filter_meta = {"tags": {"$in": tags}} if tags else None
        results = self.memory.long_term.list_recent(limit=limit, filter_metadata=filter_meta, user_id=user_id or "system")
        return results
    
    @tool(description="Recupera nota completa por ID")
    async def get_note(self, note_id: str, user_id: str | None = None) -> dict | None:
        """Recupera nota específica."""
        return self.memory.long_term.get(note_id, user_id=user_id or "system")
    
    @tool(description="Atualiza nota existente")
    async def update_note(
        self,
        note_id: str,
        content: str | None = None,
        tags: list[str] | None = None,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Atualiza nota."""
        meta = {}
        if tags is not None:
            meta["tags"] = tags
        if title is not None:
            meta["title"] = title
        if metadata is not None:
            meta.update(metadata)
        
        _uid = user_id or "system"
        if content is not None or title is not None:
            # reindexa titulo + conteudo juntos (mesma regra do save_note)
            current = self.memory.long_term.get(note_id, user_id=_uid)
            if current:
                cur_title = (current.get("metadata") or {}).get("title") or ""
                cur_body = current["content"]
                if cur_title and cur_body.startswith(cur_title + "\n"):
                    cur_body = cur_body[len(cur_title) + 1:]
                new_title = title if title is not None else cur_title
                new_body = content if content is not None else cur_body
                content = f"{new_title}\n{new_body}" if new_title and new_title.strip() else new_body
        success = self.memory.long_term.update(note_id, content=content, metadata=meta, user_id=_uid)
        return {"success": success, "id": note_id}
    
    @tool(description="Remove nota permanentemente")
    async def delete_note(self, note_id: str, user_id: str | None = None) -> dict:
        """Remove nota."""
        success = self.memory.long_term.delete(note_id, user_id=user_id or "system")
        return {"success": success, "id": note_id}


# Auto-registro
@skill("notes", "Gerencia notas e conhecimento pessoal com busca semântica", tags=["knowledge", "memory"])
class _NotesSkillWrapper(NotesSkill):
    pass