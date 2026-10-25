"""POST /computer/halt: o botao "Parar tudo" da Conversa."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from src.jefrey.core import halt as H

router = APIRouter(prefix="/computer", tags=["computer"])


@router.post("/halt")
async def halt(request: Request):
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    H.request_halt()
    return {"halted": True, "seconds": H.HALT_SECONDS}
