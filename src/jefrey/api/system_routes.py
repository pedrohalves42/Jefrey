"""Controle do programa (so existe quando o Jefrey roda pelo lancador nativo)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

router = APIRouter(prefix="/system", tags=["system"])


def _login(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    return str(uid)


@router.get("/voice")
async def voice_status(request: Request):
    """A audicao do Jefrey (voz da pessoa para texto) esta pronta? Nunca carrega o modelo."""
    _login(request)
    from src.jefrey.core import voice_ready

    return voice_ready.status()


@router.post("/voice/prepare")
async def voice_prepare(request: Request):
    """Baixa/carrega o modelo de voz em segundo plano; a tela acompanha por GET /system/voice."""
    _login(request)
    from src.jefrey.core import voice_ready

    started = voice_ready.prepare()
    return {**voice_ready.status(), "started": started}


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
