"""Conectores por programa: cada um aceita uma LISTA FECHADA de comandos com argumentos validados (nada de codigo livre)."""
from __future__ import annotations


class ConnectorError(Exception):
    """Mensagem em portugues simples, pronta para a tela."""


async def run_command(app: str, command: str, args: dict | None = None) -> str:
    from src.jefrey.core.appconnectors import blender

    connectors = {"blender": blender}
    mod = connectors.get((app or "").strip().lower())
    if mod is None:
        raise ConnectorError(f"Ainda não conheço o programa “{app}”. Eu falo com: " + ", ".join(sorted(connectors)) + ".")
    payload = mod.validate(command, args or {})
    return await mod.send(payload)
