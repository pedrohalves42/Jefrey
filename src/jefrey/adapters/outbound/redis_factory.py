"""Unico ponto que cria clientes Redis: o real (Docker/servidor) ou o local em memoria (modo nativo)."""
from __future__ import annotations

import os
from typing import Any


def is_native() -> bool:
    return (os.getenv("JEFREY_MODE", "") or "").strip().lower() == "native"


def use_local() -> bool:
    """Redis em memoria: modo nativo, ou JEFREY_REDIS__BACKEND=local (testes herméticos, sem servicos externos)."""
    return is_native() or (os.getenv("JEFREY_REDIS__BACKEND", "") or "").strip().lower() == "local"


def sync_client(url: str, **kwargs: Any):
    if use_local():
        from src.jefrey.core.local_redis import shared_sync
        return shared_sync(bool(kwargs.get("decode_responses", False)))
    import redis
    return redis.from_url(url, **kwargs)


def async_client(url: str, **kwargs: Any):
    if use_local():
        from src.jefrey.core.local_redis import shared_async
        return shared_async(bool(kwargs.get("decode_responses", False)))
    import redis.asyncio as aredis
    return aredis.from_url(url, **kwargs)
