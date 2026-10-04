"""Protecao do modo local (sem Docker): so este computador e so a propria tela do Jefrey falam com a API.

Por que existe: o servidor escuta em 127.0.0.1, mas o NAVEGADOR da pessoa tambem alcanca 127.0.0.1.
Sem isto, um site qualquer aberto na mesma maquina poderia falar com o Jefrey:
  - DNS rebinding: o site aponta o proprio dominio para 127.0.0.1 e le as respostas;
  - CSRF: o site dispara pedidos de escrita (POST/PUT/DELETE) sem poder ler a resposta;
  - WebSocket: nao passa por CORS, entao precisa checar a origem a mao.
Regras (fail-closed): Host so 127.0.0.1/localhost/[::1]; Origin so a propria tela (mesma porta);
pedidos de escrita vindos de outro site (Sec-Fetch-Site) sao recusados.
"""
from __future__ import annotations

import os
from typing import Iterable, Optional
from urllib.parse import urlsplit

from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

LOCAL_NAMES = ("127.0.0.1", "localhost", "[::1]")
DEVICE_PREFIX = "/wa/device/"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _hostname(value: str) -> str:
    """'LocalHost:8000' -> 'localhost'; '[::1]:8000' -> '[::1]'."""
    value = value.strip().lower()
    if value.startswith("["):
        end = value.find("]")
        return value[: end + 1] if end != -1 else value
    return value.rsplit(":", 1)[0] if value.count(":") == 1 else value


class LocalGuardMiddleware:
    def __init__(self, app: ASGIApp, port: Optional[int] = None, extra_hosts: Iterable[str] = (),
                 extra_origins: Iterable[str] = ()):
        self.app = app
        self.port = int(port if port is not None else os.getenv("JEFREY_API_PORT", "8000"))
        self.hosts = {h.lower() for h in LOCAL_NAMES} | {_hostname(h) for h in extra_hosts if h.strip()}
        origins = set()
        for h in LOCAL_NAMES:
            origins.add(f"http://{h}:{self.port}")
            if self.port == 80:
                origins.add(f"http://{h}")
        self.origins = origins | {o.strip().lower().rstrip("/") for o in extra_origins if o.strip()}

    def _origin_ok(self, origin: str) -> bool:
        o = origin.strip().lower().rstrip("/")
        if o in self.origins:
            return True
        parts = urlsplit(o)  # protege contra 'null' e esquemas estranhos
        return bool(parts.scheme in ("http", "https") and f"{parts.scheme}://{parts.netloc}" in self.origins)

    async def _deny(self, scope: Scope, receive: Receive, send: Send, status: int, msg: str) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        await PlainTextResponse(msg, status_code=status)(scope, receive, send)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        h = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        if _hostname(h.get("host", "")) not in self.hosts:
            await self._deny(scope, receive, send, 400, "Host nao permitido")
            return
        origin = h.get("origin")
        if scope["type"] == "websocket":
            if origin is not None and not self._origin_ok(origin):
                await self._deny(scope, receive, send, 403, "Origem nao permitida")
                return
        elif scope.get("method", "GET").upper() not in SAFE_METHODS:
            if (scope.get("path", "").startswith(DEVICE_PREFIX) and origin is not None
                    and origin.lower().startswith("chrome-extension://")):
                # a extensao do Chrome (pareada por codigo; cada pedido leva o token do aparelho). Uma pagina da web nao
                # consegue forjar o cabecalho Origin, entao so uma extensao instalada chega aqui.
                await self.app(scope, receive, send)
                return
            if origin is not None and not self._origin_ok(origin):
                await self._deny(scope, receive, send, 403, "Origem nao permitida")
                return
            if h.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
                await self._deny(scope, receive, send, 403, "Pedido de outro site recusado")
                return
        await self.app(scope, receive, send)


def local_guard_enabled() -> bool:
    """Liga no modo nativo e em qualquer execucao de desenvolvimento (onde o login /auth/dev-token existe).
    JEFREY_LOCAL_GUARD=1 forca ligar; =0 forca desligar (usado nos testes). Em producao real nao e usado."""
    flag = os.getenv("JEFREY_LOCAL_GUARD", "")
    if flag in ("0", "1"):
        return flag == "1"
    if (os.getenv("JEFREY_MODE", "") or "").strip().lower() == "native":
        return True
    return (os.getenv("JEFREY_ENV", "dev") or "dev").strip().lower() == "dev"
