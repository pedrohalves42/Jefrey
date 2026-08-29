"""Sistema de Memória - Curto e Longo Prazo."""
from __future__ import annotations
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from collections import deque

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_openai import OpenAIEmbeddings
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from src.jarvis.core.config import settings


class ShortTermMemory:
    """Buffer de conversa recente (em memória)."""
    
    def __init__(self, max_messages: int = 20, max_tokens: int = 8000):
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self._messages: deque[BaseMessage] = deque(maxlen=max_messages)
        self._token_count = 0
    
    def add(self, message: BaseMessage) -> None:
        self._messages.append(message)
        # Estimativa grosseira: 1 token ≈ 4 chars
        self._token_count += len(message.content) // 4
        self._trim()
    
    def add_user(self, content: str) -> None:
        self.add(HumanMessage(content=content))
    
    def add_assistant(self, content: str) -> None:
        self.add(AIMessage(content=content))
    
    def add_system(self, content: str) -> None:
        self.add(SystemMessage(content=content))
    
    def _trim(self) -> None:
        while self._token_count > self.max_tokens and len(self._messages) > 1:
            removed = self._messages.popleft()
            self._token_count -= len(removed.content) // 4
    
    def get_messages(self) -> list[BaseMessage]:
        return list(self._messages)
    
    def get_recent(self, n: int) -> list[BaseMessage]:
        return list(self._messages)[-n:]
    
    def clear(self) -> None:
        self._messages.clear()
        self._token_count = 0
    
    def to_dict(self) -> list[dict]:
        return [{"type": type(m).__name__, "content": m.content} for m in self._messages]


class LongTermMemory:
    """Memória vetorial persistente com ChromaDB."""
    
    def __init__(
        self,
        persist_directory: str = "data/chroma_db",
        collection_name: str = "jarvis_memory",
        embedding_model: str = "text-embedding-3-small",
        top_k: int = 5,
        similarity_threshold: float = 0.7,
    ):
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
        
        # ChromaDB client
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        
        # Embeddings
        self.embeddings = OpenAIEmbeddings(model=embedding_model)
        
        # Collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
    
    def add(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        memory_id: str | None = None,
    ) -> str:
        """Adiciona uma memória."""
        memory_id = memory_id or str(uuid.uuid4())
        metadata = metadata or {}
        metadata.setdefault("timestamp", datetime.now().isoformat())
        metadata.setdefault("type", "memory")
        
        # Gera embedding
        embedding = self.embeddings.embed_query(content)
        
        self.collection.add(
            ids=[memory_id],
            documents=[content],
            embeddings=[embedding],
            metadatas=[metadata],
        )
        return memory_id
    
    def search(
        self,
        query: str,
        top_k: int | None = None,
        filter_metadata: dict | None = None,
    ) -> list[dict]:
        """Busca semântica."""
        top_k = top_k or self.top_k
        query_embedding = self.embeddings.embed_query(query)
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filter_metadata,
            include=["documents", "metadatas", "distances"],
        )
        
        memories = []
        if results["ids"] and results["ids"][0]:
            for i, mem_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i]
                similarity = 1 - distance
                
                if similarity >= self.similarity_threshold:
                    memories.append({
                        "id": mem_id,
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "similarity": similarity,
                    })
        
        return memories
    
    def get(self, memory_id: str) -> dict | None:
        """Recupera memória por ID."""
        result = self.collection.get(ids=[memory_id], include=["documents", "metadatas"])
        if result["ids"]:
            return {
                "id": result["ids"][0],
                "content": result["documents"][0],
                "metadata": result["metadatas"][0],
            }
        return None
    
    def update(self, memory_id: str, content: str | None = None, metadata: dict | None = None) -> bool:
        """Atualiza memória."""
        existing = self.get(memory_id)
        if not existing:
            return False
        
        new_content = content or existing["content"]
        new_metadata = {**existing["metadata"], **(metadata or {})}
        new_metadata["updated_at"] = datetime.now().isoformat()
        
        embedding = self.embeddings.embed_query(new_content)
        
        self.collection.update(
            ids=[memory_id],
            documents=[new_content],
            embeddings=[embedding],
            metadatas=[new_metadata],
        )
        return True
    
    def delete(self, memory_id: str) -> bool:
        """Remove memória."""
        try:
            self.collection.delete(ids=[memory_id])
            return True
        except Exception:
            return False
    
    def list_recent(self, limit: int = 20, filter_metadata: dict | None = None) -> list[dict]:
        """Lista memórias recentes (por timestamp)."""
        results = self.collection.get(
            where=filter_metadata,
            include=["documents", "metadatas"],
            limit=limit,
        )
        
        memories = []
        if results["ids"]:
            for i, mem_id in enumerate(results["ids"]):
                memories.append({
                    "id": mem_id,
                    "content": results["documents"][i],
                    "metadata": results["metadatas"][i],
                })
        
        # Ordena por timestamp decrescente
        memories.sort(key=lambda m: m["metadata"].get("timestamp", ""), reverse=True)
        return memories


class MemoryManager:
    """Gerenciador unificado de memória."""
    
    def __init__(self):
        self.short_term = ShortTermMemory(
            max_messages=settings.memory.short_term.max_messages,
            max_tokens=settings.memory.short_term.max_tokens,
        )
        self.long_term = LongTermMemory(
            persist_directory=settings.memory.long_term.persist_directory,
            collection_name=settings.memory.long_term.collection_name,
            embedding_model=settings.memory.long_term.embedding_model,
            top_k=settings.memory.long_term.top_k,
            similarity_threshold=settings.memory.long_term.similarity_threshold,
        )
    
    def add_conversation(self, user_msg: str, assistant_msg: str) -> None:
        """Adiciona turno de conversa à memória curta."""
        self.short_term.add_user(user_msg)
        self.short_term.add_assistant(assistant_msg)
    
    def get_context(self, current_query: str) -> dict:
        """Retorna contexto combinado para o LLM."""
        # Memória relevante de longo prazo
        relevant_memories = self.long_term.search(current_query)
        
        # Histórico recente
        recent_history = self.short_term.get_messages()
        
        return {
            "chat_history": recent_history,
            "relevant_memories": relevant_memories,
            "current_datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    
    def save_important_memory(
        self,
        content: str,
        tags: list[str] | None = None,
        source: str = "conversation",
        **metadata,
    ) -> str:
        """Salva memória importante no longo prazo."""
        meta = {
            "tags": tags or [],
            "source": source,
            **metadata,
        }
        return self.long_term.add(content, metadata=meta)