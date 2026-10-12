"""Controle pelo celular (QR): ligar/desligar, gerar o codigo de pareamento, ver e revogar aparelhos. So na tela do computador."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.jefrey.adapters.outbound.phone_env import PhoneService, qr_svg
from src.jefrey.api.phone_app import build_phone_app

router = APIRouter(prefix="/phone", tags=["phone"])

_SHARED: PhoneService | None = None


def shared_service() -> PhoneService:
    global _SHARED
    if _SHARED is None:
        _SHARED = PhoneService(app_factory=build_phone_app)
    return _SHARED


def _user(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    return str(uid)


class EnabledBody(BaseModel):
    enabled: bool


def _state() -> dict:
    s = shared_service()
    return {"enabled": s.enabled, "url": s.url(), "devices": s.book.devices()}


@router.get("")
async def state(request: Request):
    _user(request)
    return _state()


@router.put("/enabled")
async def set_enabled(request: Request, body: EnabledBody):
    _user(request)
    s = shared_service()
    if body.enabled:
        if not s.start():
            raise HTTPException(status_code=409, detail="Não encontrei uma rede local (Wi-Fi ou cabo). Conecte o computador e tente de novo.")
    else:
        s.stop()
    return _state()


@router.post("/pairing")
async def pairing(request: Request):
    """Codigo de uso unico (5 min) em forma de QR. O codigo vai no FRAGMENTO do endereco: nao entra em log de servidor."""
    uid = _user(request)
    s = shared_service()
    if not s.enabled or not s.url():
        raise HTTPException(status_code=409, detail="Ligue o controle pelo celular primeiro.")
    code, ttl = s.book.issue_code(uid)
    link = f"{s.url()}/#c={code}"
    return {"qr_svg": qr_svg(link), "expires_in": int(ttl), "url": s.url()}


@router.delete("/devices/{device_id}")
async def revoke(request: Request, device_id: str):
    _user(request)
    return {"revoked": shared_service().book.revoke(device_id)}
