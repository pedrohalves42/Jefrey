"""API de lembretes (sempre do usuario logado)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reminders", tags=["reminders"])


def _user(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    return str(uid)


def _store():
    from src.jefrey.core.reminders import ReminderStore
    try:
        return ReminderStore()
    except Exception as e:
        logger.error("reminders: banco indisponivel: %s", e)
        raise HTTPException(status_code=503, detail="Não consegui acessar os lembretes agora.")


@router.get("")
async def list_pending(request: Request):
    items = _store().pending(_user(request))
    return {"reminders": items, "count": len(items)}


@router.get("/due")
async def list_due(request: Request):
    """Lembretes que ja venceram e ainda nao foram confirmados (o app consulta de tempos em tempos)."""
    items = _store().due(_user(request))
    return {"reminders": items, "count": len(items)}


@router.post("/{reminder_id}/ack")
async def ack(reminder_id: str, request: Request):
    """O app mostrou o lembrete: sai da fila (os repetidos vao para a proxima vez)."""
    if not _store().ack(_user(request), reminder_id):
        raise HTTPException(status_code=404, detail="lembrete nao encontrado")
    return {"ok": True}


@router.delete("/{reminder_id}")
async def cancel(reminder_id: str, request: Request):
    if not _store().cancel(_user(request), reminder_id):
        raise HTTPException(status_code=404, detail="lembrete nao encontrado")
    return {"ok": True}
