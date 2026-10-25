"""Controle do programa (so existe quando o Jefrey roda pelo lancador nativo)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field

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


class OpenBody(BaseModel):
    url: str = Field(max_length=2000)


@router.post("/open-external")
async def open_external(body: OpenBody, request: Request):
    """Abre no navegador de verdade (o Google nao deixa entrar por dentro da janela do app). So enderecos do Google."""
    _login(request)
    from src.jefrey.native import shell

    if not shell.open_external(body.url):
        raise HTTPException(status_code=422, detail="endereco nao permitido")
    return {"ok": True}


class AutostartBody(BaseModel):
    enabled: bool


@router.get("/autostart")
async def autostart_status(request: Request):
    _login(request)
    from src.jefrey.native import autostart

    return {"available": autostart.available(), "enabled": autostart.is_enabled()}


@router.put("/autostart")
async def autostart_set(body: AutostartBody, request: Request):
    _login(request)
    from src.jefrey.native import autostart

    if not autostart.available():
        raise HTTPException(status_code=404, detail="so no programa instalado")
    ok = autostart.set_enabled(body.enabled)
    return {"available": True, "enabled": autostart.is_enabled(), "ok": ok}


@router.get("/shell")
async def shell_info(request: Request):
    """A tela esta dentro da janela propria do app (e nao em um navegador)? Quem sabe e o programa."""
    _login(request)
    from src.jefrey.native import control

    return {"window": control.has_window()}


@router.post("/orb")
async def show_orb(request: Request):
    _login(request)
    from src.jefrey.native import control

    if not control.show_orb():
        raise HTTPException(status_code=404, detail="indisponivel neste modo")
    return {"ok": True}


@router.post("/messages")
async def open_messages(request: Request):
    """Abre a janela de Mensagens (WhatsApp Web dentro do Jefrey) para a pessoa logada."""
    uid = _login(request)
    from src.jefrey.native import control

    if not control.open_messages(uid):
        raise HTTPException(status_code=404, detail="indisponivel neste modo")
    return {"ok": True}


@router.post("/site/{net_id}")
async def open_site(net_id: str, request: Request):
    """Abre a janela de uma rede social dentro do Jefrey (WhatsApp, Instagram, Facebook, X, Telegram)."""
    uid = _login(request)
    from src.jefrey.domain.social import NETWORKS
    from src.jefrey.native import control

    if net_id not in NETWORKS:
        raise HTTPException(status_code=404, detail="rede desconhecida")
    ok = control.open_messages(uid) if net_id == "whatsapp" else control.open_site(net_id)
    if not ok:
        raise HTTPException(status_code=404, detail="indisponivel neste modo")
    return {"ok": True}


@router.post("/restart")
async def restart_app(request: Request, background: BackgroundTasks):
    """Fecha e abre o Jefrey de novo (so no programa instalado/nativo)."""
    _login(request)
    from src.jefrey.native import control

    if not control.can_restart():
        raise HTTPException(status_code=404, detail="indisponivel neste modo")
    background.add_task(control.request_restart)  # depois de responder
    return {"ok": True, "message": "O Jefrey vai reiniciar."}


@router.post("/show")
async def show_window(request: Request):
    _login(request)
    from src.jefrey.native import control

    return {"ok": control.show_window()}
