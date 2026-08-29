"""Entrypoint para `python -m src.jefrey.mcp` (processo separado do MCP Server)."""
from src.jefrey.mcp.server import main

if __name__ == "__main__":
    main()
