"""Controle do programa (so existe quando o Jefrey roda pelo lancador nativo)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

router = APIRouter(prefix="/system", tags=["system"])


@router.post("/quit")
async def quit_app(request: Request, background: BackgroundTasks):
    """Fecha o Jefrey. Exige login; responde 404 fora do modo nativo (servidor/Docker nao fecham por aqui)."""
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    from src.jefrey.native import control

    if not control.can_quit():
        raise HTTPException(status_code=404, detail="indisponivel neste modo")
    background.add_task(control.request_quit)  # depois de responder, para a tela receber o aviso
    return {"ok": True, "message": "O Jefrey vai fechar."}
