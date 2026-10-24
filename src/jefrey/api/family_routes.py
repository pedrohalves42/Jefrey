"""Modo familia: ligar/desligar e escolher quem recebe o resumo semanal. Desligado por padrao."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.jefrey.application.family import shared_store

router = APIRouter(prefix="/family", tags=["family"])


def _user(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    return str(uid)


class ConsentBody(BaseModel):
    enabled: bool
    contact: str = Field(default="", max_length=80)


@router.get("")
async def state(request: Request):
    c = shared_store().get(_user(request))
    return {"enabled": c["enabled"], "contact": c["contact"]}


@router.put("")
async def set_consent(request: Request, body: ConsentBody):
    c = shared_store().set_consent(_user(request), body.enabled, body.contact)
    return {"enabled": c["enabled"], "contact": c["contact"]}
