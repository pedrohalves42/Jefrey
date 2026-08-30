"""Working memory (curto prazo) apoiada em Redis com fallback em memoria local."""
from __future__ import annotations

import json
import logging
import threading
from collections import deque
from typing import Any, Optional

logger = logging.getLogger(__name__)

_MESSAGE_TYPES = {
    "HumanMessage": "human",
    "AIMessage": "ai",
    "SystemMessage": "system",
    "ToolMessage": "tool",
}
_TYPE_TO_CLASS: dict[str, Any] = {}

def _message_classes() -> dict[str, Any]:
    if not _TYPE_TO_CLASS:
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

        _TYPE_TO_CLASS.update(
            {
                "human": HumanMessage,
                "ai": AIMessage,
                "system": SystemMessage,
                "tool": ToolMessage,
            }
        )
    return _TYPE_TO_CLASS

def _serialize(msg) -> dict:
    return {"role": _MESSAGE_TYPES.get(type(msg).__name__, "human"), "content": msg.content}

def _deserialize(d: dict):
    # Popula (preguicosamente) o mapa role->classe antes de desserializar.
    # Sem isso, _TYPE_TO_CLASS ficaria vazio e _TYPE_TO_CLASS["human"] levantaria KeyError.
    classes = _message_classes()
    cls = classes.get(d["role"])
    if cls is None:
        cls = classes.get("human")
    if cls is None:
        raise ValueError(f"tipo de mensagem desconhecido: {d.get('role')!r}")
    return cls(d["content"])

class RedisWorkingMemory:
    """Memoria de trabalho por sessao (thread_id). Redis como primario, memoria local como fallback."""

    def __init__(
        self,
        session_id: str = "default",
        max_messages: int = 20,
        max_tokens: int = 8000,
        redis_url: Optional[str] = None,
        redis_client=None,
        prefix: str = "jefrey:wm:",
    ):
        self.session_id = session_id
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.prefix = prefix
        self._lock = threading.RLock()
        self._local: dict[str, list[dict]] = {}
        self._redis = redis_client
        if self._redis is None and redis_url is not None:
            try:
                import redis

                self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
            except Exception as e:  # pragma: no cover - resiliencia
                logger.warning(
                    "Redis indisponivel (%s) -- usando memoria local para sessao '%s'",
                    e,
                    session_id,
                )
                self._redis = None

    # ---- escopo por sessao ----
    def session(self, session_id: str) -> "RedisWorkingMemory":
        return RedisWorkingMemory(
            session_id=session_id,
            max_messages=self.max_messages,
            max_tokens=self.max_tokens,
            redis_client=self._redis,
            prefix=self.prefix,
        )

    # ---- armazenamento ----
    def _key(self) -> str:
        return f"{self.prefix}{self.session_id}"

    def _load(self) -> list[dict]:
        if self._redis is not None:
            raw = self._redis.get(self._key())
            return json.loads(raw) if raw else []
        return self._local.setdefault(self.session_id, [])

    def _save(self, items: list[dict]) -> None:
        if self._redis is not None:
            self._redis.set(self._key(), json.dumps(items))
        else:
            self._local[self.session_id] = items

    # ---- API publica (compativel com ShortTermMemory) ----
    def add(self, message) -> None:
        with self._lock:
            items = self._load()
            items.append(_serialize(message))
            self._trim(items)
            self._save(items)

    def add_user(self, content: str) -> None:
        from langchain_core.messages import HumanMessage

        self.add(HumanMessage(content=content))

    def add_assistant(self, content: str) -> None:
        from langchain_core.messages import AIMessage

        self.add(AIMessage(content=content))

    def add_system(self, content: str) -> None:
        from langchain_core.messages import SystemMessage

        self.add(SystemMessage(content=content))

    def _trim(self, items: list[dict]) -> None:
        total = sum(len(i["content"]) // 4 for i in items if isinstance(i.get("content"), str))
        while (total > self.max_tokens or len(items) > self.max_messages) and len(items) > 1:
            removed = items.pop(0)
            if isinstance(removed.get("content"), str):
                total -= len(removed["content"]) // 4

    def get_messages(self) -> list:
        with self._lock:
            return [_deserialize(i) for i in self._load()]

    def get_recent(self, n: int) -> list:
        return self.get_messages()[-n:]

    def clear(self) -> None:
        with self._lock:
            if self._redis is not None:
                self._redis.delete(self._key())
            else:
                self._local[self.session_id] = []

    def to_dict(self) -> list[dict]:
        with self._lock:
            return [{"type": i["role"], "content": i["content"]} for i in self._load()]

    def __len__(self) -> int:
        return len(self._load())

    @property
    def token_count(self) -> int:
        return sum(
            len(i["content"]) // 4 for i in self._load() if isinstance(i.get("content"), str)
        )

    def list_sessions(self) -> list[str]:
        if self._redis is not None:
            return [k.replace(self.prefix, "") for k in self._redis.keys(f"{self.prefix}*")]
        return list(self._local.keys())

    def health_check(self) -> dict:
        """Verifica saude do backend de working memory.

        Retorna 'ok' (Redis acessivel com auth), 'local_fallback' (Redis indisponivel,
        usando memoria local) ou 'error' (falha inesperada ao pingar o Redis).
        """
        if self._redis is None:
            return {"status": "local_fallback", "backend": "local"}
        try:
            # SECURITY: ping valida nao apenas conectividade mas tambem autenticacao
            self._redis.ping()
            # Verifica se auth funciona realmente (ping pode passar sem auth em configs sem senha)
            self._redis.echo(b"health")
            return {"status": "ok", "backend": "redis"}
        except Exception as e:  # noqa: BLE001
            logger.warning("health_check redis falhou: %s", e)
            return {"status": "error", "backend": "redis", "error": str(e)}
