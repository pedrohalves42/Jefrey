"""Perfil da pessoa: como o Jefrey deve chama-la."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileBody(BaseModel):
    display_name: str = Field(min_length=1, max_length=60)


def _user(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    return str(uid)


@router.get("")
async def get_profile(request: Request):
    from src.jefrey.core.profile import ProfileStore

    return {"display_name": ProfileStore().get_name(_user(request))}


@router.put("")
async def put_profile(body: ProfileBody, request: Request):
    from src.jefrey.core.profile import ProfileStore

    try:
        return {"display_name": ProfileStore().set_name(_user(request), body.display_name)}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("")
async def delete_profile(request: Request):
    from src.jefrey.core.profile import ProfileStore

    ProfileStore().clear_name(_user(request))
    return {"ok": True}
