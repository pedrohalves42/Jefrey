"""Servidor MCP externo de DEMONSTRAÇÃO (stdio) para provar o Jefrey MCPClient.

Este é um servidor MCP *real* (processo filho spawnado via stdio), mas propositalmente
simples e independente do Jefrey — ele NÃO é o Jefrey MCP Server (evita loopback da
Opção A). Simula um "provedor de ferramentas externo" contra o qual o MCPClient do
Jefrey se conecta em P3c.

Usa o high-level MCPServer (mcp 2.x) — o mesmo padrão de src/jefrey/mcp/server.py —
rodando sobre transporte stdio.

Ferramentas expostas:
  * add(a:int, b:int) -> str(a+b)
  * echo(text:str)    -> str(text)
  * jefrey_ping()     -> "pong"

Uso pelo Jefrey MCPClient (stdio):
  MCPClient(command=[sys.executable, "scripts/mcp_external_demo_server.py"])
"""
from __future__ import annotations

import logging

logging.basicConfig(level=logging.WARNING)

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("jefrey-external-demo")


@mcp.tool(name="add", description="Soma dois inteiros e retorna o resultado como texto.")
async def add(a: int, b: int) -> str:
    return str(a + b)


@mcp.tool(name="echo", description="Devolve o texto recebido (eco).")
async def echo(text: str) -> str:
    return text


@mcp.tool(name="jefrey_ping", description="Healthcheck do servidor externo.")
async def jefrey_ping() -> str:
    return "pong"


if __name__ == "__main__":
    mcp.run(transport="stdio")
