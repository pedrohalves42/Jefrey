"""Tarefas em segundo plano do Jefrey (estudos, briefing...). Roda dentro do proprio programa, so enquanto ele esta aberto.

Cada tarefa tem um intervalo; uma falha nunca derruba o laco nem as outras tarefas.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

Job = Callable[[], Awaitable[None]]
_jobs: list[tuple[str, float, Job]] = []
_task: Optional[asyncio.Task] = None
_last_run: dict[str, float] = {}
TICK_S = 30.0


def register(name: str, every_s: float, fn: Job) -> None:
    _jobs[:] = [j for j in _jobs if j[0] != name]
    _jobs.append((name, every_s, fn))


async def run_due(now: Optional[float] = None) -> list[str]:
    """Roda as tarefas vencidas. Devolve os nomes que rodaram (usado nos testes)."""
    now = time.monotonic() if now is None else now
    ran: list[str] = []
    for name, every, fn in list(_jobs):
        if now - _last_run.get(name, -1e12) < every:
            continue
        _last_run[name] = now
        try:
            await fn()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("tarefa %s falhou: %s", name, type(e).__name__)
        ran.append(name)
    return ran


async def _loop() -> None:
    await asyncio.sleep(60)  # deixa o programa abrir e a pessoa comecar
    while True:
        await run_due()
        await asyncio.sleep(TICK_S)


def enabled() -> bool:
    return os.getenv("JEFREY_SCHEDULER", "1") != "0" and "PYTEST_CURRENT_TEST" not in os.environ


def start() -> None:
    global _task
    if not enabled() or (_task is not None and not _task.done()):
        return
    _task = asyncio.get_running_loop().create_task(_loop(), name="jefrey-scheduler")


def stop() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        _task = None
