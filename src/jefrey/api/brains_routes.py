"""Cerebros do Jefrey: conectar varios servicos, escolher o principal e desconectar (tudo em linguagem simples)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.jefrey.core import brains as B

router = APIRouter(prefix="/brains", tags=["brains"])


def _login(request: Request) -> None:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")


class ConnectBody(BaseModel):
    api_key: Optional[str] = Field(default=None, max_length=500)


class RolesBody(BaseModel):
    roles: Optional[list[str]] = Field(default=None, max_length=12)  # None = serve para tudo


@router.get("")
async def list_brains(request: Request):
    _login(request)
    return B.state()


@router.get("/check")
async def check(request: Request):
    """Testa de verdade cada cerebro (uma palavra) e diz quem funciona, quanto demora e, se falhar, o motivo."""
    _login(request)
    return {"results": await B.check_all()}


@router.put("/team")
async def team(body: RolesBody, request: Request):
    """Funcoes em que dois cerebros trabalham juntos."""
    _login(request)
    return B.set_team(body.roles or [])


@router.put("/{brain_id}/roles")
async def roles(brain_id: str, body: RolesBody, request: Request):
    """O que este cerebro faz (conversar, ferramentas, escrever...)."""
    _login(request)
    try:
        return B.set_roles(brain_id, body.roles)
    except B.BrainError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{brain_id}/connect")
async def connect(brain_id: str, body: ConnectBody, request: Request):
    _login(request)
    try:
        return await B.connect(brain_id, body.api_key)
    except B.BrainError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/{brain_id}/primary")
async def primary(brain_id: str, request: Request):
    _login(request)
    try:
        return B.make_primary(brain_id)
    except B.BrainError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{brain_id}")
async def disconnect(brain_id: str, request: Request):
    _login(request)
    try:
        return B.disconnect(brain_id)
    except B.BrainError as e:
        raise HTTPException(status_code=404, detail=str(e))
