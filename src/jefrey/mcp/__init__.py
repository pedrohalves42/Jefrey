"""Pacote MCP do Jefrey (Fase P3a/P3b) — gateway de ferramentas via MCP."""
from src.jefrey.mcp.server import build_server, main, INTEGRATION_TOOLS
from src.jefrey.mcp.n8n_bridge import N8nBridge, get_bridge, WorkflowResult

__all__ = ["build_server", "main", "INTEGRATION_TOOLS", "N8nBridge", "get_bridge", "WorkflowResult"]
