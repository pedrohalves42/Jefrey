"""Compatibilidade de event loop entre Windows e Linux/macOS.

Importar e chamar `configure_event_loop()` antes de qualquer uso de asyncio em
entrypoints (scripts de verificação, `python -m src.jefrey.mcp`, futuros FastAPI).
"""
from __future__ import annotations

import sys
import asyncio


def configure_event_loop() -> None:
    """Configura a política de event loop adequada à plataforma.

    No Windows, o psycopg v3 async exige SelectorEventLoop (o ProactorEventLoop
    padrão não suporta alguns transports/operações). No Linux/macOS o default já é
    SelectorEventLoop — não fazemos nada.

    Nota: WindowsSelectorEventLoopPolicy está deprecated no Python 3.16 (Windows);
    revisar na migração para a nova loop API.
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
