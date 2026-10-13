"""Area de transferencia inteligente: ligar/desligar, ver a oferta, pedir a acao e dispensar. Desligada por padrao."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.jefrey.application.clipboard import shared_store

router = APIRouter(prefix="/clipboard", tags=["clipboard"])


def _user(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    return str(uid)


class EnabledBody(BaseModel):
    enabled: bool


class ActionBody(BaseModel):
    action: str = Field(..., max_length=20)


@router.get("")
async def state(request: Request):
    _user(request)
    s = shared_store()
    offer = s.get()
    view = {"preview": offer["text"][:200], "offers": offer["offers"]} if offer else None
    return {"enabled": s.enabled(), "offer": view}


@router.put("/enabled")
async def set_enabled(request: Request, body: EnabledBody):
    _user(request)
    shared_store().set_enabled(body.enabled)
    return {"enabled": shared_store().enabled()}


@router.post("/prompt")
async def prompt(request: Request, body: ActionBody):
    """Pedido pronto para a conversa: o texto copiado entra como DADO."""
    _user(request)
    try:
        return {"prompt": shared_store().prompt(body.action)}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/dismiss")
async def dismiss(request: Request):
    _user(request)
    shared_store().dismiss()
    return {"ok": True}
