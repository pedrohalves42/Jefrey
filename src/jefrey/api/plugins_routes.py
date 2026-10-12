"""Plugins: a pessoa ve os arquivos em config/plugins, aprova (pelo hash que viu) ou revoga."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.jefrey.adapters.outbound.plugin_env import shared_store

router = APIRouter(prefix="/plugins", tags=["plugins"])


def _user(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    return str(uid)


class ApproveBody(BaseModel):
    sha256: str = Field(..., min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")


@router.get("")
async def listing(request: Request):
    _user(request)
    return {"plugins": shared_store().scan()}


@router.post("/{name}/approve")
async def approve(name: str, body: ApproveBody, request: Request):
    _user(request)
    if not shared_store().approve(name, body.sha256):
        raise HTTPException(status_code=409, detail="o arquivo mudou ou nao existe: confira de novo antes de aprovar")
    return {"loaded": shared_store().load_approved()}


@router.delete("/{name}")
async def revoke(name: str, request: Request):
    _user(request)
    return {"revoked": shared_store().revoke(name)}
