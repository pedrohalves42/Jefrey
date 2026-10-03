"""Memory Layers for Jefrey AI Agent
Implements hierarchical memory structure inspired by isair/jarvis pattern.
Contains 3 layers: Working, Semantic, and Episodic memory.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from enum import Enum


class MemoryLayer(Enum):
    """Enumeration of memory layer types."""
    WORKING = "working"
    SEMANTIC = "semantic"
    EPISODIC = "episodic"


class MemoryRecord:
    """Base class for memory records across all layers."""
    
    def __init__(
        self,
        content: str,
        layer: MemoryLayer,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ):
        self.content = content
        self.layer = layer
        self.metadata = metadata or {}
        self.timestamp = timestamp or datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert memory record to dictionary."""
        return {
            "content": self.content,
            "layer": self.layer.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }
    
    def __repr__(self) -> str:
        return f"<MemoryRecord layer={self.layer.value} timestamp={self.timestamp}>"


class WorkingMemory(MemoryRecord):
    """Working memory layer - temporary, fast-access storage.
    
    Inspired by isair/jarvis working memory concept.
    Holds transient information for current operations.
    """
    
    def __init__(
        self,
        content: str,
        ttl_minutes: int = 30,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            content=content,
            layer=MemoryLayer.WORKING,
            metadata={"ttl_minutes": ttl_minutes, **metadata},
        )


class SemanticMemory(MemoryRecord):
    """Semantic memory layer - persistent knowledge base.
    
    Inspired by isair/jarvis semantic memory concept.
    Stores factual knowledge and concepts learned over time.
    """
    
    def __init__(
        self,
        content: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            content=content,
            layer=MemoryLayer.SEMANTIC,
            metadata={"tags": tags or [], **metadata},
        )


class EpisodicMemory(MemoryRecord):
    """Episodic memory layer - event-based storage.
    
    Inspired by isair/jarvis episodic memory concept.
    Stores discrete events and experiences with timestamps.
    """
    
    def __init__(
        self,
        content: str,
        event_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            content=content,
            layer=MemoryLayer.EPISODIC,
            metadata={"event_id": event_id or "auto", **(metadata or {})},
        )


class MemoryManager:
    """Manager orchestrating all memory layers.
    
    Coordinates between working, semantic, and episodic memory
    providing a unified interface for memory operations.
    """
    
    def __init__(
        self,
        working_ttl_minutes: int = 30,
        semantic_storage=None,
        episodic_storage=None,
    ):
        self.working_ttl_minutes = working_ttl_minutes
        self.working_memory: Dict[str, WorkingMemory] = {}
        self.semantic_memory: List[SemanticMemory] = semantic_memory or []
        self.episodic_memory: List[EpisodicMemory] = episodic_memory or []
        self._creation_counter = 0
    
    def store_working(self, content: str, key: str = None, ttl_minutes: int = None) -> WorkingMemory:
        """Store information in working memory.
        
        Args:
            content: The content to store
            key: Optional key for retrieval
            ttl_minutes: TTL in minutes (defaults to class default)
        
        Returns:
            WorkingMemory: The stored record
        """
        ttl = ttl_minutes or self.working_ttl_minutes
        record = WorkingMemory(content=content, ttl_minutes=ttl)
        key = key or f"working_{self._creation_counter}"
        self._creation_counter += 1
        self.working_memory[key] = record
        return record
    
    def retrieve_working(self, key: str) -> Optional[WorkingMemory]:
        """Retrieve working memory by key.
        
        Args:
            key: The key to retrieve
        
        Returns:
            WorkingMemory or None if not found
        """
        return self.working_memory.get(key)
    
    def expire_working(self, key: str) -> bool:
        """Expire working memory entry by key.
        
        Args:
            key: The key to expire
        
        Returns:
            bool: True if expired, False if not found
        """
        if key in self.working_memory:
            del self.working_memory[key]
            return True
        return False
    
    def store_semantic(self, content: str, tags: List[str] = None) -> SemanticMemory:
        """Store information in semantic memory.
        
        Args:
            content: The content to store
            tags: Optional tags for retrieval
        
        Returns:
            SemanticMemory: The stored record
        """
        record = SemanticMemory(content=content, tags=tags)
        self.semantic_memory.append(record)
        return record
    
    def retrieve_semantic(self, tags: List[str] = None) -> List[SemanticMemory]:
        """Retrieve semantic memory by tags.
        
        Args:
            tags: Optional tags to filter by
        
        Returns:
            List[SemanticMemory]: Matching records
        """
        if tags:
            return [m for m in self.semantic_memory if any(t in m.metadata.get("tags", []) for t in tags)]
        return self.semantic_memory[:]
    
    def store_episodic(self, content: str, event_id: str = None) -> EpisodicMemory:
        """Store information in episodic memory.
        
        Args:
            content: The content to store
            event_id: Optional event ID
        
        Returns:
            EpisodicMemory: The stored record
        """
        record = EpisodicMemory(content=content, event_id=event_id or f"evt_{self._creation_counter}")
        self._creation_counter += 1
        self.episodic_memory.append(record)
        return record
    
    def retrieve_episodic(self, event_id: str = None) -> List[EpisodicMemory]:
        """Retrieve episodic memory by event ID.
        
        Args:
            event_id: Optional event ID to filter by
        
        Returns:
            List[EpisodicMemory]: Matching records
        """
        if event_id:
            return [m for m in self.episodic_memory if m.metadata.get("event_id") == event_id]
        return self.episodic_memory[:]
    
    def get_all_memories(self) -> Dict[str, List[Any]]:
        """Get all memories across all layers.
        
        Returns:
            Dict[str, List[Any]]: Dictionary with memories from each layer
        """
        return {
            "working": list(self.working_memory.values()),
            "semantic": self.semantic_memory,
            "episodic": self.episodic_memory,
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about memory usage.
        
        Returns:
            Dict[str, Any]: Statistics dictionary
        """
        return {
            "working_count": len(self.working_memory),
            "semantic_count": len(self.semantic_memory),
            "episodic_count": len(self.episodic_memory),
            "total_count": len(self.working_memory) + len(self.semantic_memory) + len(self.episodic_memory),
        }


# Global memory manager instance
_managed_memory: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get the global memory manager instance."""
    global _managed_memory
    if _managed_memory is None:
        _managed_memory = MemoryManager()
    return _managed_memory


def init_memory() -> MemoryManager:
    """Initialize the global memory manager."""
    global _managed_memory
    _managed_memory = MemoryManager()
    return _managed_memory


# Convenience functions for direct usage
def store_working(content: str, key: str = None, ttl_minutes: int = 30) -> WorkingMemory:
    """Store content in working memory."""
    return get_memory_manager().store_working(content, key, ttl_minutes)


def retrieve_working(key: str) -> Optional[WorkingMemory]:
    """Retrieve working memory by key."""
    return get_memory_manager().retrieve_working(key)


def store_semantic(content: str, tags: List[str] = None) -> SemanticMemory:
    """Store content in semantic memory."""
    return get_memory_manager().store_semantic(content, tags)


def retrieve_semantic(tags: List[str] = None) -> List[SemanticMemory]:
    """Retrieve semantic memory by tags."""
    return get_memory_manager().retrieve_semantic(tags)


def store_episodic(content: str, event_id: str = None) -> EpisodicMemory:
    """Store content in episodic memory."""
    return get_memory_manager().store_episodic(content, event_id)


def retrieve_episodic(event_id: str = None) -> List[EpisodicMemory]:
    """Retrieve episodic memory by event ID."""
    return get_memory_manager().retrieve_episodic(event_id)


# Convenience aliases for the memory layer types
working_memory = WorkingMemory
semantic_memory = SemanticMemory
episodic_memory = EpisodicMemory