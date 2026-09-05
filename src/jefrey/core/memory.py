"""Sistema de Memória Otimizado - Curto e Longo Prazo."""
from __future__ import annotations
import json
import uuid
import threading
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from collections import deque
from contextlib import contextmanager

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_openai import OpenAIEmbeddings
from langchain_ollama import OllamaEmbeddings
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from src.jefrey.core.config import get_settings

# Ativa logging estruturado (JSON) ao carregar o subsistema de memória.
import src.jefrey.core.logging  # noqa: F401

# Remove module-level settings call to avoid import-time initialization
# Use get_settings() lazily inside functions/classes instead


class _EmbeddingCache:
    """Cache simples de embeddings para evitar chamadas repetidas."""
    
    def __init__(self, maxsize: int = 1000):
        self._cache: dict[str, list[float]] = {}
        self._lock = threading.Lock()
        self._maxsize = maxsize
    
    def get(self, text: str) -> list[float] | None:
        with self._lock:
            return self._cache.get(text)
    
    def set(self, text: str, embedding: list[float]) -> None:
        with self._lock:
            if len(self._cache) >= self._maxsize:
                # Remove item mais antigo (FIFO simples)
                self._cache.pop(next(iter(self._cache)))
            self._cache[text] = embedding

_embedding_cache = _EmbeddingCache()


def _create_embeddings():
    """Cria instância de embeddings baseada na configuração."""
    s = get_settings()
    emb_settings = s.embeddings
    llm_settings = s.llm
    
    # Se provider for ollama, usa OllamaEmbeddings
    if llm_settings.provider == "ollama":
        return OllamaEmbeddings(
            model=emb_settings.model,
            base_url=emb_settings.base_url,
        )
    # Senão usa OpenAI
    return OpenAIEmbeddings(
        model=emb_settings.model,
        api_key=emb_settings.api_key or llm_settings.api_key,
        base_url=emb_settings.base_url,
    )


class CachedEmbeddings:
    """Wrapper com cache para qualquer provedor de embeddings."""
    
    def __init__(self, base_embeddings):
        self._base = base_embeddings
    
    def embed_query(self, text: str) -> list[float]:
        cached = _embedding_cache.get(text)
        if cached is not None:
            return cached
        embedding = self._base.embed_query(text)
        _embedding_cache.set(text, embedding)
        return embedding
    
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        results = []
        uncached_texts = []
        uncached_indices = []
        
        for i, text in enumerate(texts):
            cached = _embedding_cache.get(text)
            if cached is not None:
                results.append(cached)
            else:
                results.append(None)
                uncached_texts.append(text)
                uncached_indices.append(i)
        
        if uncached_texts:
            new_embeddings = self._base.embed_documents(uncached_texts)
            for idx, emb in zip(uncached_indices, new_embeddings):
                results[idx] = emb
                _embedding_cache.set(uncached_texts[uncached_indices.index(idx)], emb)
        
        return results


# Instância global de embeddings
_embeddings_instance = None
_embeddings_lock = threading.Lock()

def get_embeddings():
    """Retorna instância singleton de embeddings com cache."""
    global _embeddings_instance
    if _embeddings_instance is None:
        with _embeddings_lock:
            if _embeddings_instance is None:
                base = _create_embeddings()
                _embeddings_instance = CachedEmbeddings(base)
    return _embeddings_instance


def _to_chroma_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Converte valores não primitivos (list/dict) em strings JSON para compatibilidade com ChromaDB.

    ChromaDB aceita apenas str, int, float, bool em metadados. Valores complexos são
    serializados para JSON e desserializados em `_from_chroma_metadata` na leitura.
    """
    if not metadata:
        return {}
    sanitized: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, (list, dict)):
            sanitized[key] = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, (str, int, float, bool)) or value is None:
            sanitized[key] = value
        else:
            sanitized[key] = str(value)
    return sanitized


def _from_chroma_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Tenta reconstruir valores complexos serializados por `_to_chroma_metadata`."""
    if not metadata:
        return {}
    restored: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, str) and value and value[0] in ("[", "{"):
            try:
                restored[key] = json.loads(value)
                continue
            except (json.JSONDecodeError, TypeError) as _e:  # not JSON, keep raw # OK: typed fallback
                logger.debug("metadata JSON decode fallback: %s", _e) if "logger" in dir() else None
        restored[key] = value
    return restored


class ShortTermMemory:
    """Buffer de conversa recente (em memória) - Thread-safe."""
    
    __slots__ = ("_messages", "_token_count", "_max_messages", "_max_tokens", "_lock")
    
    def __init__(self, max_messages: int = 20, max_tokens: int = 8000):
        self._max_messages = max_messages
        self._max_tokens = max_tokens
        self._messages: deque[BaseMessage] = deque(maxlen=max_messages)
        self._token_count = 0
        self._lock = threading.RLock()
    
    def add(self, message: BaseMessage) -> None:
        with self._lock:
            self._messages.append(message)
            # Estimativa: 1 token ≈ 4 chars (português)
            self._token_count += len(message.content) // 4
            self._trim()
    
    def add_user(self, content: str) -> None:
        self.add(HumanMessage(content=content))
    
    def add_assistant(self, content: str) -> None:
        self.add(AIMessage(content=content))
    
    def add_system(self, content: str) -> None:
        self.add(SystemMessage(content=content))
    
    def _trim(self) -> None:
        while self._token_count > self._max_tokens and len(self._messages) > 1:
            removed = self._messages.popleft()
            self._token_count -= len(removed.content) // 4
    
    def get_messages(self) -> list[BaseMessage]:
        with self._lock:
            return list(self._messages)
    
    def get_recent(self, n: int) -> list[BaseMessage]:
        with self._lock:
            return list(self._messages)[-n:]
    
    def clear(self) -> None:
        with self._lock:
            self._messages.clear()
            self._token_count = 0
    
    def to_dict(self) -> list[dict]:
        with self._lock:
            return [{"type": type(m).__name__, "content": m.content} for m in self._messages]
    
    def __len__(self) -> int:
        with self._lock:
            return len(self._messages)
    
    @property
    def token_count(self) -> int:
        with self._lock:
            return self._token_count


class ChromaConnectionPool:
    """Pool de conexões ChromaDB para reuso eficiente."""
    
    _instance: "ChromaConnectionPool | None" = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._client: chromadb.PersistentClient | None = None
        self._collections: dict[str, chromadb.Collection] = {}
        self._lock = threading.RLock()
        self._initialized = True
    
    def get_client(self) -> chromadb.PersistentClient:
        with self._lock:
            if self._client is None:
                s = get_settings()
                self._client = chromadb.PersistentClient(
                    path=s.memory.long_term.persist_directory,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
            return self._client
    
    def get_collection(self, name: str) -> chromadb.Collection:
        with self._lock:
            if name not in self._collections:
                client = self.get_client()
                self._collections[name] = client.get_or_create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"},
                )
            return self._collections[name]
    
    def reset(self) -> None:
        with self._lock:
            self._collections.clear()
            self._client = None


class LongTermMemory:
    """Memória vetorial persistente com ChromaDB - Otimizada."""
    
    __slots__ = ("_top_k", "_similarity_threshold", "_embeddings", "_collection")
    
    def __init__(
        self,
        persist_directory: str | None = None,
        collection_name: str | None = None,
        embedding_model: str | None = None,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
    ):
        s = get_settings()
        self._top_k = top_k or s.memory.long_term.top_k
        self._similarity_threshold = similarity_threshold or s.memory.long_term.similarity_threshold
        
        # Embeddings com cache (usando factory)
        self._embeddings = get_embeddings()
        
        # Pool de conexões
        pool = ChromaConnectionPool()
        s = get_settings()
        self._collection = pool.get_collection(
            collection_name or s.memory.long_term.collection_name
        )
    
    def add(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        memory_id: str | None = None,
        user_id: str | None = None,
    ) -> str:
        """Adiciona uma memória."""
        memory_id = memory_id or str(uuid.uuid4())
        metadata = metadata or {}
        # H2: Isolar por user_id no metadata para fallback ChromaDB
        if user_id:
            metadata.setdefault("user_id", user_id)
        metadata.setdefault("timestamp", datetime.now().isoformat())
        metadata.setdefault("type", "memory")
        metadata = _to_chroma_metadata(metadata)

        embedding = self._embeddings.embed_query(content)

        self._collection.add(
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
        user_id: str | None = None,
    ) -> list[dict]:
        """Busca semântica otimizada."""
        top_k = top_k or self._top_k
        query_embedding = self._embeddings.embed_query(query)
        
        # H2: Construir where clause com filtro user_id
        where = filter_metadata or {}
        if user_id:
            where["user_id"] = user_id
        
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        
        memories = []
        if results["ids"] and results["ids"][0]:
            for i, mem_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i]
                similarity = 1 - distance
                
                if similarity >= self._similarity_threshold:
                    memories.append({
                        "id": mem_id,
                        "content": results["documents"][0][i],
                        "metadata": _from_chroma_metadata(results["metadatas"][0][i]),
                        "similarity": round(similarity, 4),
                    })
        
        return memories
    
    def get(self, memory_id: str) -> dict | None:
        """Recupera memória por ID."""
        result = self._collection.get(ids=[memory_id], include=["documents", "metadatas"])
        if result["ids"]:
            return {
                "id": result["ids"][0],
                "content": result["documents"][0],
                "metadata": _from_chroma_metadata(result["metadatas"][0]),
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
        new_metadata = _to_chroma_metadata(new_metadata)
        
        embedding = self._embeddings.embed_query(new_content)
        
        self._collection.update(
            ids=[memory_id],
            documents=[new_content],
            embeddings=[embedding],
            metadatas=[new_metadata],
        )
        return True
    
    def delete(self, memory_id: str) -> bool:
        """Remove memória."""
        try:
            self._collection.delete(ids=[memory_id])
            return True
        except Exception:
            return False
    
    def list_recent(self, limit: int = 20, filter_metadata: dict | None = None) -> list[dict]:
        """Lista memórias recentes (por timestamp)."""
        results = self._collection.get(
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
                    "metadata": _from_chroma_metadata(results["metadatas"][i]),
                })
        
        memories.sort(key=lambda m: m["metadata"].get("timestamp", ""), reverse=True)
        return memories
    
    def health_check(self) -> dict:
        """Verifica saúde do backend ChromaDB (contagem + captura de erro)."""
        import logging

        log = logging.getLogger(__name__)
        try:
            n = self._collection.count()
            return {"status": "ok", "backend": "chromadb", "count": n}
        except Exception as e:  # noqa: BLE001
            log.error("health_check chromadb falhou: %s", e)
            return {"status": "error", "backend": "chromadb", "error": str(e)}

    def count(self) -> int:
        """Total de memórias armazenadas."""
        return self._collection.count()


class MemoryManager:
    """Gerenciador unificado de memória - Facade principal."""
    
    def __init__(self):
        s = get_settings()
        lt = s.memory.long_term

        # Working memory (curto prazo) — Redis com fallback em memória local
        from src.jefrey.core.redis_memory import RedisWorkingMemory

        self.short_term = RedisWorkingMemory(
            session_id="default",
            max_messages=s.memory.short_term.max_messages,
            max_tokens=s.memory.short_term.max_tokens,
            redis_url=s.redis.dsn,
        )

        # Long-term memory (vetorial) — Postgres+pgvector ou ChromaDB (fallback)
        if lt.provider in ("postgres", "postgresql"):
            from src.jefrey.core.pg_memory import PostgresLongTermMemory

            self.long_term = PostgresLongTermMemory()
        else:
            self.long_term = LongTermMemory()
    
    def add_conversation(self, user_msg: str, assistant_msg: str) -> None:
        """Adiciona turno de conversa à memória curta."""
        self.short_term.add_user(user_msg)
        self.short_term.add_assistant(assistant_msg)
    
    def get_context(self, current_query: str, user_id: str | None = None) -> dict:
        """Retorna contexto combinado para o LLM."""
        relevant_memories = self.long_term.search(current_query, user_id=user_id)
        recent_history = self.short_term.get_messages()
        
        return {
            "chat_history": recent_history,
            "relevant_memories": relevant_memories,
            "current_datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "short_term_stats": {
                "messages": len(self.short_term),
                "tokens": self.short_term.token_count,
            },
            "long_term_stats": {
                "total_memories": self.long_term.count(user_id=user_id),
            },
        }
    
    def save_important_memory(
        self,
        content: str,
        tags: list[str] | None = None,
        source: str = "conversation",
        user_id: str | None = None,
        **metadata,
    ) -> str:
        """Salva memória importante no longo prazo."""
        meta = {
            "tags": tags or [],
            "source": source,
            **metadata,
        }
        return self.long_term.add(content, metadata=meta, user_id=user_id)
    
    def clear_short_term(self) -> None:
        self.short_term.clear()

    def health_check(self) -> dict:
        """Verifica saúde de curto e longo prazo (Postgres + Redis).

        Status 'healthy' se ambos os backends responderem; 'degraded' se algum
        estiver em erro. Expõe detalhes por backend para observabilidade/monitoramento.
        """
        import logging

        log = logging.getLogger(__name__)
        pg = self.long_term.health_check()
        rd = self.short_term.health_check()
        status = "healthy"
        if pg.get("status") == "error" or rd.get("status") == "error":
            status = "degraded"
        log.info("health_check status=%s postgres=%s redis=%s", status, pg.get("status"), rd.get("status"))
        return {
            "status": status,
            "postgres": pg,
            "redis": rd,
            "default_layer": getattr(self.long_term, "_default_layer", "chromadb"),
        }


# Instância global (singleton)
_memory_manager: MemoryManager | None = None
_memory_lock = threading.Lock()

def get_memory_manager() -> MemoryManager:
    """Retorna instância singleton do gerenciador de memória."""
    global _memory_manager
    if _memory_manager is None:
        with _memory_lock:
            if _memory_manager is None:
                _memory_manager = MemoryManager()
    return _memory_manager


def safe_deserialize(data: dict) -> BaseMessage:
    """Converte um dict {'type': 'human', 'content': '...'} em um objeto BaseMessage.

    Evita KeyError ao usar verificações if/elif pelos tipos conhecidos.
    """
    msg_type = data.get("type", "")
    content = data.get("content", "")
    if msg_type == "human":
        return HumanMessage(content=content)
    if msg_type == "ai":
        return AIMessage(content=content)
    if msg_type == "system":
        return SystemMessage(content=content)
    if msg_type == "tool":
        return ToolMessage(content=content, role=data.get("role", "tool"))
    raise ValueError(f"Tipo de mensagem desconhecido: {msg_type}")





# ----------------------------------------------------------------------
# Lazy message registry – evita KeyError em _deserialize
# ----------------------------------------------------------------------
_message_registry: dict[str, type] = {}
_registry_initialized: bool = False


def _init_message_registry() -> None:
    """Popula _message_registry com tipos BaseMessage. Chamado sob demanda."""
    global _registry_initialized
    if _registry_initialized:
        return
    from langchain_core.messages import (
        HumanMessage,
        AIMessage,
        SystemMessage,
        ToolMessage,
    )
    _message_registry = {
        "human": HumanMessage,
        "ai": AIMessage,
        "system": SystemMessage,
        "tool": ToolMessage,
    }
    _registry_initialized = True





