"""Chamadas HTTP de saida (GET/POST) com tempo limite, para quem fala com servicos de fora (n8n, Google, OpenRouter...).
Os testes trocam `httpx.AsyncClient` por um falso: por isso o cliente e criado a cada chamada."""
from __future__ import annotations

from typing import Any

import httpx

Response = httpx.Response
HTTPError = httpx.HTTPError
Timeout = httpx.Timeout


def client(timeout: Any = 10, **kw: Any) -> httpx.AsyncClient:
    """Um cliente novo a cada uso (os testes trocam `httpx.AsyncClient` por um falso)."""
    return httpx.AsyncClient(timeout=timeout, **kw)


async def get(url: str, *, timeout: float = 10, **kw: Any) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as c:
        return await c.get(url, **kw)


async def post(url: str, *, timeout: float = 10, **kw: Any) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as c:
        return await c.post(url, **kw)
