"""Painel "Hoje": GET /today (tudo do dia) e PUT /today/region (cidade e estado). Ver core/today.py."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.jefrey.core import today as T

router = APIRouter(prefix="/today", tags=["today"])


def _login(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    return uid


class RegionBody(BaseModel):
    city: str = Field(..., max_length=60)
    uf: str = Field(..., max_length=2)


@router.get("")
async def today(request: Request):
    return await T.build(user_id=_login(request))


@router.put("/region")
async def set_region(request: Request, body: RegionBody):
    _login(request)
    try:
        T.save_prefs(body.city, body.uf)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return T.load_prefs()
