"""Checkpointer Postgres para LangGraph (Fase P2).

Substitui o `MemorySaver` em memória por persistência real em PostgreSQL, usando o
`AsyncPostgresSaver` do `langgraph-checkpoint-postgres`. As tabelas (`checkpoints`,
`checkpoint_writes`, `checkpoint_blobs`) são criadas de forma idempotente por `setup()`.

IMPORTANTE (Windows): o psycopg v3 em modo assíncrono exige `SelectorEventLoop`
(`ProactorEventLoop` padrão do Windows não é suportado). Qualquer ponto de entrada
assíncrono que use este checkpointer deve executar sob `SelectorEventLoop`, ex.:

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # win32
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
"""
from __future__ import annotations

import asyncio
from typing import Optional

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.jefrey.core.config import get_settings

_saver: Optional[AsyncPostgresSaver] = None
_cm = None  # context manager retornado por from_conn_string (para fechar o pool)
_lock = asyncio.Lock()


def _psycopg_dsn() -> str:
    """DSN psycopg puro ('postgresql://') a partir do DSN SQLAlchemy ('postgresql+psycopg://')."""
    return get_settings().database.dsn.replace("+psycopg", "")


async def get_postgres_checkpointer() -> AsyncPostgresSaver:
    """Retorna (e cria, se necessário) um único AsyncPostgresSaver compartilhado.

    Cria as tabelas de checkpoint uma única vez via `setup()` (idempotente).
    """
    global _saver, _cm
    if _saver is None:
        async with _lock:
            if _saver is None:
                _cm = AsyncPostgresSaver.from_conn_string(_psycopg_dsn())
                _saver = await _cm.__aenter__()
                await _saver.setup()
    return _saver


async def close_postgres_checkpointer() -> None:
    """Fecha o pool e libera o saver compartilhado."""
    global _saver, _cm
    if _cm is not None:
        try:
            await _cm.__aexit__(None, None, None)
        finally:
            _cm = None
            _saver = None
