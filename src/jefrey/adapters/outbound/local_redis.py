"""Redis em memoria, no mesmo processo, para o modo nativo (sem Docker).

So implementa os comandos que o Jefrey usa (historico de conversa, memoria de trabalho, limite de uso,
fila). Valores expiram como no Redis; tudo vive apenas enquanto o Jefrey esta aberto (o historico de
conversa tem validade de 24 h de qualquer forma; memorias e notas ficam em disco, em outro lugar).
"""
from __future__ import annotations

import fnmatch
import threading
import time
from typing import Any, Callable, Optional

_MAX_KEYS = 20000  # teto de seguranca: nunca cresce sem limite


class _Store:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self.lock = threading.RLock()
        self.data: dict[str, Any] = {}
        self.expiry: dict[str, float] = {}
        self.seq = 0

    def alive(self, key: str) -> bool:
        exp = self.expiry.get(key)
        if exp is not None and exp <= self.clock():
            self.data.pop(key, None)
            self.expiry.pop(key, None)
            return False
        return key in self.data

    def trim(self) -> None:
        if len(self.data) > _MAX_KEYS:
            for k in list(self.data)[: len(self.data) - _MAX_KEYS]:
                self.data.pop(k, None)
                self.expiry.pop(k, None)


def _s(v: Any) -> str:
    return v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else str(v)


class LocalRedis:
    """Cliente sincrono compativel com o subconjunto usado do `redis.Redis`."""

    def __init__(self, store: Optional[_Store] = None, decode_responses: bool = False):
        self._st = store or _Store()
        self._decode = decode_responses

    def _out(self, v: Any) -> Any:
        if isinstance(v, str) and not self._decode:
            return v.encode("utf-8")
        return v

    # ---- basico
    def ping(self) -> bool:
        return True

    def get(self, key: str):
        with self._st.lock:
            return self._out(self._st.data[key]) if self._st.alive(key) and isinstance(self._st.data[key], str) else None

    def set(self, key: str, value: Any, ex: Optional[int] = None, **_: Any) -> bool:
        with self._st.lock:
            self._st.data[key] = _s(value)
            if ex:
                self._st.expiry[key] = self._st.clock() + float(ex)
            else:
                self._st.expiry.pop(key, None)
            self._st.trim()
        return True

    def setex(self, key: str, ttl: int, value: Any) -> bool:
        return self.set(key, value, ex=ttl)

    def delete(self, *keys: str) -> int:
        with self._st.lock:
            n = 0
            for k in keys:
                if self._st.alive(k):
                    n += 1
                self._st.data.pop(k, None)
                self._st.expiry.pop(k, None)
            return n

    def expire(self, key: str, ttl: int) -> bool:
        with self._st.lock:
            if not self._st.alive(key):
                return False
            self._st.expiry[key] = self._st.clock() + float(ttl)
            return True

    def ttl(self, key: str) -> int:
        with self._st.lock:
            if not self._st.alive(key):
                return -2
            exp = self._st.expiry.get(key)
            return -1 if exp is None else max(0, int(round(exp - self._st.clock())))

    def incr(self, key: str) -> int:
        with self._st.lock:
            cur = int(self._st.data[key]) if self._st.alive(key) else 0
            self._st.data[key] = str(cur + 1)
            return cur + 1

    # ---- listas
    def rpush(self, key: str, *values: Any) -> int:
        with self._st.lock:
            if not self._st.alive(key) or not isinstance(self._st.data.get(key), list):
                self._st.data[key] = []
            self._st.data[key].extend(_s(v) for v in values)
            self._st.trim()
            return len(self._st.data[key])

    def lrange(self, key: str, start: int, end: int) -> list:
        with self._st.lock:
            if not self._st.alive(key) or not isinstance(self._st.data[key], list):
                return []
            lst = self._st.data[key]
            n = len(lst)
            s = max(n + start, 0) if start < 0 else start
            e = n + end if end < 0 else end
            return [self._out(v) for v in lst[s:e + 1]]

    def ltrim(self, key: str, start: int, end: int) -> bool:
        with self._st.lock:
            if self._st.alive(key) and isinstance(self._st.data[key], list):
                lst = self._st.data[key]
                n = len(lst)
                s = max(n + start, 0) if start < 0 else start
                e = n + end if end < 0 else end
                self._st.data[key] = lst[s:e + 1]
            return True

    # ---- varredura e fila
    def scan(self, cursor: int = 0, match: str = "*", count: int = 100):
        with self._st.lock:
            keys = [k for k in list(self._st.data) if self._st.alive(k) and fnmatch.fnmatchcase(k, match)]
        return 0, [self._out(k) for k in keys]

    def xadd(self, key: str, fields: dict, maxlen: Optional[int] = None, approximate: bool = True, **_: Any) -> str:
        with self._st.lock:
            self._st.seq += 1
            ident = f"{int(time.time() * 1000)}-{self._st.seq}"
            if not self._st.alive(key) or not isinstance(self._st.data.get(key), list):
                self._st.data[key] = []
            self._st.data[key].append((ident, dict(fields)))
            if maxlen:
                del self._st.data[key][:-int(maxlen)]
            return ident

    def xlen(self, key: str) -> int:
        with self._st.lock:
            return len(self._st.data[key]) if self._st.alive(key) and isinstance(self._st.data[key], list) else 0

    # ---- pipeline (executa em ordem, devolve a lista de resultados)
    def pipeline(self, transaction: bool = True) -> "_Pipeline":
        return _Pipeline(self)


class _Pipeline:
    def __init__(self, client: LocalRedis):
        self._c = client
        self._ops: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, name: str):
        if name.startswith("_") or not hasattr(self._c, name):
            raise AttributeError(name)

        def queue(*a, **kw):
            self._ops.append((name, a, kw))
            return self
        return queue

    def multi(self) -> None:
        return None

    def execute(self) -> list:
        ops, self._ops = self._ops, []
        with self._c._st.lock:  # atomico
            return [getattr(self._c, n)(*a, **kw) for n, a, kw in ops]


class AsyncLocalRedis:
    """Versao assincrona (mesmo armazenamento) para `redis.asyncio`."""

    def __init__(self, store: Optional[_Store] = None, decode_responses: bool = False):
        self._c = LocalRedis(store, decode_responses)

    def __getattr__(self, name: str):
        attr = getattr(self._c, name)
        if name == "pipeline":
            def pipe(*a, **kw):
                return _AsyncPipeline(attr(*a, **kw))
            return pipe

        async def call(*a, **kw):
            return attr(*a, **kw)
        return call


class _AsyncPipeline:
    def __init__(self, inner: _Pipeline):
        self._p = inner

    def __getattr__(self, name: str):
        fn = getattr(self._p, name)
        if name == "execute":
            async def run():
                return fn()
            return run

        def queue(*a, **kw):
            fn(*a, **kw)
            return self
        return queue


_SHARED = _Store()  # um unico armazenamento por processo, compartilhado entre todos os clientes


def shared_sync(decode_responses: bool = False) -> LocalRedis:
    return LocalRedis(_SHARED, decode_responses)


def shared_async(decode_responses: bool = False) -> AsyncLocalRedis:
    return AsyncLocalRedis(_SHARED, decode_responses)
