"""Atualizacoes: ver se ha versao nova e instalar (so quando a pessoa clica)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from src.jefrey.core import updater as U

router = APIRouter(prefix="/updates", tags=["updates"])


def _login(request: Request) -> None:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")


@router.get("/check")
async def check(request: Request):
    _login(request)
    try:
        return await U.check()
    except U.UpdateError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/install")
async def install(request: Request, background: BackgroundTasks):
    """Baixa, confere a assinatura e o hash, faz backup e roda o instalador. O programa fecha para a instalacao."""
    _login(request)
    from src.jefrey.native import control

    if not control.can_quit():
        raise HTTPException(status_code=404, detail="A atualização automática só funciona no programa instalado.")
    try:
        res = await U.install()
    except U.UpdateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    background.add_task(control.request_quit)  # o instalador reabre o Jefrey ao terminar
    return res
