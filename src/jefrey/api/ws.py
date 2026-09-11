# src/jefrey/api/ws.py – Broadcast de eventos para interface gráfica 3D (Phase 10)
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set

# Gerenciador de conexões WebSocket (singleton por instância do app)
class WSManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active.discard(ws)

    async def broadcast(self, message: dict) -> None:
        """Envia um dicionário JSON para todos os clientes conectados."""
        if not self.active:
            return
        # Usa asyncio.gather para não bloquear o loop principal
        await asyncio.gather(
            *[
                ws.send_json(message)
                for ws in self.active
                if ws.application_state == "connected"  # type: ignore
            ],
            return_exceptions=True,
        )

# Instância global (lazy import na aplicação)
_ws_manager: WSManager | None = None

def get_ws_manager() -> WSManager:
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WSManager()
    return _ws_manager

# Funções de conveniência (podem ser importadas por agent.py, hitl.py, etc.)
async def publish_tool_start(tool_name: str, user_id: str) -> None:
    manager = get_ws_manager()
    await manager.broadcast({
        "type": "tool_start",
        "tool": tool_name,
        "user_id": user_id,
    })

async def publish_memory_retrieved(query: str, user_id: str, results: int) -> None:
    manager = get_ws_manager()
    await manager.broadcast({
        "type": "memory_retrieved",
        "query": query,
        "user_id": user_id,
        "results": results,
    })

async def publish_approval_pending(approval_id: str, user_id: str) -> None:
    manager = get_ws_manager()
    await manager.broadcast({
        "type": "approval_pending",
        "approval_id": approval_id,
        "user_id": user_id,
    })

async def publish_security_alert(event: str, detail: str, user_id: str) -> None:
    manager = get_ws_manager()
    await manager.broadcast({
        "type": "security_alert",
        "event": event,
        "detail": detail,
        "user_id": user_id,
    })