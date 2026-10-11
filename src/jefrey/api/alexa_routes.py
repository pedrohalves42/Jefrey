"""Tela Conexoes > Alexa: cadastrar token e dispositivos do Voice Monkey, testar e desconectar."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.jefrey.core import alexa as A

router = APIRouter(prefix="/alexa", tags=["alexa"])


def _login(request: Request) -> None:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")


class AlexaBody(BaseModel):
    token: Optional[str] = Field(default=None, max_length=200)  # None mantem o atual
    devices: dict[str, str] = Field(default_factory=dict)
    routines: dict[str, str] = Field(default_factory=dict)


@router.get("")
async def get_alexa(request: Request):
    _login(request)
    return A.status()


@router.put("")
async def put_alexa(body: AlexaBody, request: Request):
    _login(request)
    try:
        A.save(body.token, body.devices, body.routines)
    except A.AlexaError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return A.status()


@router.post("/test")
async def test_alexa(request: Request):
    """Faz o primeiro aparelho falar uma frase curta (so a pessoa pode pedir; nao e uma ferramenta do modelo)."""
    _login(request)
    try:
        msg = await A.say("Olá! Aqui é o Jefrey. A conexão com a Alexa está funcionando.")
    except A.AlexaError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"ok": True, "message": msg}


@router.delete("")
async def delete_alexa(request: Request):
    _login(request)
    A.clear()
    return A.status()
