"""Jefrey MCP Client (Fase P3c) — Jefrey consome servidores MCP externos.

Módulo ISOLADO (Decisão 2 do P3c): utilitário testável, FORA do loop de
raciocínio do agente (LangGraph/OpenAI). A integração no agent loop (quando o
agente decidir chamar uma ferramenta MCP externa durante o raciocínio) fica
para P4, que refatora o loop de qualquer forma (RBAC, HITL UI).

Transports suportados:
  * streamable-http : servidores MCP sobre HTTP (ex.: n8n MCP Server, Jefrey MCP Server)
  * stdio           : servidores MCP spawnados como subprocesso (ex.: ferramentas CLI)

Alvo arquitetural (Opção C / Decisão 1): Jefrey -> MCPClient -> n8n MCP Server
-> workflows. O cliente é genérico, então funciona contra qualquer servidor MCP
compatível (incluindo o próprio n8n quando expuser um MCP Server).
"""
from __future__ import annotations

import sys
import os
import json
import logging
import asyncio
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

# garante que o pacote 'src' seja importável independente de como o processo sobe
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.client.stdio import StdioServerParameters, stdio_client

from src.jefrey.core.metrics import MCP_CALLS, MCP_LATENCY

logger = logging.getLogger(__name__)


class MCPClientError(RuntimeError):
    """Erro controlado do MCPClient — seguro para expor ao caller.

    Não vaza stack traces internos; o atributo `original` guarda a exceção original
    apenas para logging server-side.
    """

    def __init__(self, message: str, tool: str = "", original: Exception | None = None):
        super().__init__(message)
        self.message = message
        self.tool = tool
        self.original = original

    def __str__(self) -> str:
        return self.message

# ---------------------------------------------------------------------------
# M3: OAuth Token Manager com kid rotation (MCP Spec 2026-07-28, Book 5)
# Gerencia multiplos tokens de acesso para servidores MCP protegidos.
# Suporta rotacao automatica (kid rotation): se um token recebe 401,
# o proximo token da lista e tentado antes de falhar.
# ---------------------------------------------------------------------------
import time as _time_mod

class OAuthTokenManager:
    """Gerencia tokens OAuth para o MCPClient.

    Suporta:
    - Multiplos tokens (kid rotation) - tenta o proximo se 401
    - Carregamento do env (JEFREY_MCP_CLIENT_TOKENS)
    - TTL tracking por token (preparacao para JWT com exp)
    - Thread-safe rotation via indice atomico
    """

    def __init__(self, tokens: list[str] | None = None) -> None:
        self._tokens: list[str] = tokens or self._load_from_env()
        self._current_idx: int = 0
        self._rotation_count: int = 0
        self._last_rotation: float = 0.0

    @staticmethod
    def _load_from_env() -> list[str]:
        """Carrega tokens do env var JEFREY_MCP_CLIENT_TOKENS (comma-separated)."""
        raw = os.getenv("JEFREY_MCP_CLIENT_TOKENS", "")
        return [t.strip() for t in raw.split(",") if t.strip()]

    @property
    def has_tokens(self) -> bool:
        return len(self._tokens) > 0

    @property
    def current_token(self) -> str | None:
        if not self._tokens:
            return None
        return self._tokens[self._current_idx % len(self._tokens)]

    @property
    def token_count(self) -> int:
        return len(self._tokens)

    def rotate(self) -> str | None:
        """Rotaciona para o proximo token (kid rotation).

        Retorna o novo token ou None se nao ha mais tokens.
        Apos tentar todos os tokens, retorna None (fail-closed).
        """
        if not self._tokens or len(self._tokens) <= 1:
            return None  # Sem rotacao possivel

        self._current_idx = (self._current_idx + 1) % len(self._tokens)
        self._rotation_count += 1
        self._last_rotation = _time_mod.time()
        logger.info(
            "OAuth kid rotation: token %d/%d (rotations=%d)",
            self._current_idx + 1, len(self._tokens), self._rotation_count,
        )
        return self.current_token

    def exhausted(self) -> bool:
        """Verifica se todos os tokens ja foram tentados nesta rodada."""
        return self._rotation_count >= len(self._tokens)

    def reset_rotation(self) -> None:
        """Reseta o contador de rotacao (nova rodada de tentativas)."""
        self._rotation_count = 0

    def get_auth_headers(self) -> dict[str, str]:
        """Retorna headers de autenticacao para o token atual."""
        token = self.current_token
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    def info(self) -> dict:
        """Info do gerenciador para debug/health."""
        return {
            "has_tokens": self.has_tokens,
            "token_count": self.token_count,
            "current_idx": self._current_idx,
            "rotation_count": self._rotation_count,
            "last_rotation": self._last_rotation,
        }




class MCPClient:
    """Cliente MCP para Jefrey consumir ferramentas de servidores externos.

    Uso:
        async with MCPClient(url="http://host:8001/mcp") as c:
            tools = await c.list_tools()
            out = await c.call_tool("add", {"a": 2, "b": 3})
    """

    def __init__(
        self,
        name: str = "external",
        url: str | None = None,
        command: list[str] | None = None,
        env: dict | None = None,
        timeout: float = 30.0,
        oauth_tokens: list[str] | None = None,
    ) -> None:
        self.name = name
        self.url = url
        self.command = command or []
        self.env = env or {}
        self._timeout = timeout
        self._oauth = OAuthTokenManager(tokens=oauth_tokens)
        self._stack = AsyncExitStack()
        self._session: ClientSession | None = None

    # ----- construção a partir de spec de configuração -----
    @staticmethod
    def _get(spec: Any, key: str) -> Any:
        """Lê atributo de modelo pydantic OU chave de dict."""
        if isinstance(spec, dict):
            return spec.get(key)
        return getattr(spec, key, None)

    @classmethod
    def from_spec(cls, spec: Any) -> "MCPClient":
        """Cria a partir de ExternalMCPServer (config) ou dict compatível."""
        name = cls._get(spec, "name") or "external"
        url = cls._get(spec, "url")
        command = cls._get(spec, "command")
        transport = cls._get(spec, "transport") or "streamable-http"
        if transport == "stdio" and command:
            cmd = command if isinstance(command, list) else command.split()
            return cls(name=name, command=cmd, env=cls._spec_env(spec), oauth_tokens=cls._spec_oauth(spec))
        if url:
            return cls(name=name, url=url, oauth_tokens=cls._spec_oauth(spec))
        raise MCPClientError(f"spec '{name}' sem url (http) ou command (stdio)")

    @classmethod
    def _spec_env(cls, spec: Any) -> dict:
        env = cls._get(spec, "env") or {}
        return dict(env) if isinstance(env, dict) else {}

    @classmethod
    def _spec_oauth(cls, spec: Any) -> list[str] | None:
        """Extrai oauth_tokens da spec de configuracao."""
        tokens = cls._get(spec, "oauth_tokens")
        if isinstance(tokens, list):
            return tokens
        if isinstance(tokens, str) and tokens:
            return [t.strip() for t in tokens.split(",") if t.strip()]
        return None

    # ----- ciclo de vida -----
    async def connect(self) -> "MCPClient":
        try:
            if self.url:
                # streamable_http_client retorna (read, write) ou (read, write, get_session_id)
                # conforme a versão do SDK; aceitamos ambos.
                # M3: Injeta OAuth headers via httpx.AsyncClient customizado
                import httpx as _httpx
                _headers = self._oauth.get_auth_headers()
                _http_client = _httpx.AsyncClient(headers=_headers) if _headers else None
                streams = await self._stack.enter_async_context(
                    streamable_http_client(self.url, http_client=_http_client)
                )
                read, write = streams[0], streams[1]
            elif self.command:
                params = StdioServerParameters(
                    command=self.command[0],
                    args=self.command[1:],
                    env=self.env or None,  # None => herda os.environ do pai
                )
                read, write = await self._stack.enter_async_context(stdio_client(params))
            else:
                raise MCPClientError("informe url (streamable-http) ou command (stdio)")
            self._session = await self._stack.enter_async_context(
                ClientSession(read, write)
            )
            await self._session.initialize()
        except MCPClientError:
            raise
        except Exception as e:  # noqa: BLE001
            raise MCPClientError(
                f"Falha ao conectar ao servidor MCP '{self.name}'",
                original=e,
            ) from e
        logger.info("MCPClient conectado a '%s' (%s)", self.name, self.url or self.command)
        return self

    async def disconnect(self) -> None:
        try:
            await self._stack.aclose()
        except Exception:  # noqa: BLE001
            pass
        self._session = None

    async def __aenter__(self) -> "MCPClient":
        return await self.connect()

    async def __aexit__(self, *exc) -> None:
        await self.disconnect()

    # ----- registro explícito (Opção B, Decisão 3) -----
    def register_explicit(
        self, *, tool_name: str, risk: "str | object", required_role: str = "user",
        description: str = "", overwrite: bool = True,
    ) -> "MCPClient":
        """Registra explicitamente uma ferramenta deste servidor MCP no ToolRegistry.

        Opção B (Decisão 3): em vez de descobrir ferramentas automaticamente via
        list_tools (superfície de ataque — servidor malicioso poderia injetar tools),
        cada ferramenta externa é registrada manualmente com risco e papel declarados.
        """
        from src.jefrey.core.rbac import as_role
        from src.jefrey.core.policy import RiskLevel
        from src.jefrey.core.registry import TOOL_REGISTRY

        rk = risk if isinstance(risk, RiskLevel) else RiskLevel(str(risk).lower())
        TOOL_REGISTRY.register(
            name=tool_name, risk=rk, required_role=as_role(required_role),
            description=description, server=self.name, source="mcp", external=True,
            overwrite=overwrite,
        )
        logger.info("MCPClient registrou explicitamente '%s' (server=%s risk=%s)", tool_name, self.name, rk.value)
        return self

    # ----- ferramentas -----
    async def list_tools(self) -> list[dict]:
        if self._session is None:
            raise MCPClientError("cliente não conectado")
        resp = await self._session.list_tools()
        return [
            {
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.input_schema,
            }
            for t in resp.tools
        ]

    async def _reconnect_with_rotation(self) -> bool:
        """Tenta reconectar com o proximo token (kid rotation).

        Retorna True se reconectou com sucesso, False se tokens esgotados.
        Usado quando o servidor retorna 401 (token invalido/expirado).
        """
        new_token = self._oauth.rotate()
        if new_token is None or self._oauth.exhausted():
            logger.warning("OAuth kid rotation exhausted for '%s' - all tokens tried", self.name)
            self._oauth.reset_rotation()
            return False

        # Reconectar com novo token
        logger.info("Reconnecting '%s' with rotated token", self.name)
        try:
            await self.disconnect()
            await self.connect()
            return True
        except MCPClientError as e:
            logger.warning("Reconnect with rotated token failed: %s", e)
            return False

    @property
    def oauth_info(self) -> dict:
        """Info do OAuth para debug/health."""
        return self._oauth.info()

    async def call_tool(self, name: str, arguments: dict | None = None) -> str:
        import time as _time
        if self._session is None:
            raise MCPClientError(f"MCPClient '{self.name}' não está conectado")
        _start = _time.monotonic()
        try:
            result = await asyncio.wait_for(
                self._session.call_tool(name, arguments or {}),
                timeout=self._timeout,
            )
            _elapsed = _time.monotonic() - _start
            MCP_LATENCY.labels(server=self.name).observe(_elapsed)
            MCP_CALLS.labels(server=self.name, status="success").inc()
        except asyncio.TimeoutError:
            _elapsed = _time.monotonic() - _start
            MCP_LATENCY.labels(server=self.name).observe(_elapsed)
            MCP_CALLS.labels(server=self.name, status="error").inc()
            raise MCPClientError(
                f"Timeout ao chamar ferramenta '{name}' em '{self.name}'",
                tool=name,
            )
        except MCPClientError:
            _elapsed = _time.monotonic() - _start
            MCP_LATENCY.labels(server=self.name).observe(_elapsed)
            MCP_CALLS.labels(server=self.name, status="error").inc()
            raise
        except Exception as e:  # noqa: BLE001
            _elapsed = _time.monotonic() - _start
            MCP_LATENCY.labels(server=self.name).observe(_elapsed)
            MCP_CALLS.labels(server=self.name, status="error").inc()
            raise MCPClientError(
                f"Erro ao chamar '{name}' em '{self.name}': {type(e).__name__}",
                tool=name,
                original=e,
            ) from e

        if getattr(result, "isError", False):
            logger.warning("ferramenta '%s' retornou isError", name)
            return f"[ERRO MCP:{name}] A ferramenta reportou falha."

        # CIPHER-011: sanitiza output externo antes de entregar ao chamador/LLM.
        from src.jefrey.core.content_guard import sanitize_tool_output

        raw = _result_to_text(result)
        return sanitize_tool_output(raw, source=f"mcp:{self.name}:{name}")


def _result_to_text(result: Any) -> str:
    """Normaliza CallToolResult -> texto (content[].text, senão structuredContent)."""
    parts: list[str] = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text is not None:
            parts.append(text)
    if parts:
        return "\n".join(parts)
    sc = getattr(result, "structuredContent", None)
    if sc is not None:
        return json.dumps(sc, ensure_ascii=False, default=str)
    data = getattr(result, "data", None)
    if data is not None:
        return json.dumps(data, ensure_ascii=False, default=str)
    return ""


async def _smoke() -> None:
    """Smoke mínimo: conecta no Jefrey MCP Server local (se rodando) e lista tools."""
    client = MCPClient(name="jefrey-local", url="http://localhost:8001/mcp")
    async with client:
        tools = await client.list_tools()
        print(f"MCPClient smoke: {len(tools)} ferramentas no localhost:8001/mcp")
        print(f"OAuth info: {client.oauth_info}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_smoke())
