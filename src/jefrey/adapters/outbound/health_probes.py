"""Sondas de saude do Redis e do banco. So perguntam e respondem; quem decide e a rota."""
from __future__ import annotations

from typing import Any


def redis_ping(dsn: str) -> None:
    """Levanta se o Redis nao responde."""
    import redis as _redis

    _redis.Redis.from_url(dsn or "redis://localhost:6379").ping()


async def database_ping(dsn: str) -> bool:
    """SQLite local (modo nativo) ou Postgres (asyncpg, com psycopg de reserva). Levanta se nao conectar."""
    if str(dsn or "").startswith("sqlite"):
        from sqlalchemy import text

        from src.jefrey.core.db import get_engine

        with get_engine().connect() as c:
            c.execute(text("SELECT 1"))
        return True
    pg = (dsn or "postgresql://localhost/jefrey").replace("postgresql+psycopg://", "postgresql://")
    try:
        import asyncpg

        conn: Any = await asyncpg.connect(pg)
        await conn.close()
    except ImportError:
        import psycopg

        psycopg.connect(pg).close()
    return True
