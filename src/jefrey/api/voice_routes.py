"""Voz do Jefrey: escolhe o melhor motor (nuvem -> local -> navegador) e cuida do download da voz natural local."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.jefrey.core import cloudvoice as CV
from src.jefrey.core import localvoice as LV

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])

_download: dict = {"state": "idle", "pct": 0, "error": ""}
_task: Optional[asyncio.Task] = None


def _login(request: Request) -> None:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")


class SpeakBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    engine: Optional[str] = Field(default=None, pattern="^(cloud|local)$")


@router.get("/engines")
async def engines(request: Request):
    _login(request)
    cloud, local = CV.available(), LV.available()
    items = [
        {"id": "cloud", "available": cloud, "label": "Natural (nuvem, conta do ChatGPT)"},
        {"id": "local", "available": local, "label": "Natural (neste computador)"},
        {"id": "browser", "available": True, "label": "Voz do computador"},
    ]
    return {"engines": items, "default": "cloud" if cloud else "local" if local else "browser", "local": LV.model_status()}


@router.post("/speak")
async def speak(request: Request, body: SpeakBody):
    _login(request)
    order = [body.engine] if body.engine else ["cloud", "local"]
    last = ""
    for eng in order:
        if eng == "cloud" and CV.available():
            try:
                return Response(content=await CV.synth(body.text), media_type="audio/mpeg", headers={"X-Voice-Engine": "cloud", "Cache-Control": "no-store"})
            except CV.CloudVoiceError as e:
                last = str(e)
        elif eng == "local" and LV.available():
            try:
                audio = await asyncio.to_thread(LV.synth, body.text)
                return Response(content=audio, media_type="audio/wav", headers={"X-Voice-Engine": "local", "Cache-Control": "no-store"})
            except LV.LocalVoiceError as e:
                last = str(e)
    raise HTTPException(status_code=409, detail=last or "Nenhuma voz natural está pronta. Vou usar a voz do computador.")


@router.get("/local")
async def local_status(request: Request):
    _login(request)
    return {**LV.model_status(), **_download}


@router.post("/local/download")
async def start_download(request: Request):
    """Baixa a voz natural (uma vez, ~60 MB). O progresso sai em GET /voice/local."""
    global _task
    _login(request)
    if _download["state"] == "running":
        return dict(_download)
    _download.update(state="running", pct=0, error="")

    def progress(p: int) -> None:
        _download["pct"] = p

    async def work() -> None:
        try:
            await LV.download_model(progress=progress)
            _download.update(state="done", pct=100)
        except LV.LocalVoiceError as e:
            _download.update(state="error", error=str(e))
        except Exception as e:  # nada solto: a tela sempre recebe uma frase simples
            logger.warning("voz local: download falhou (%s)", type(e).__name__)
            _download.update(state="error", error="Não consegui baixar a voz agora. Tente de novo.")

    _task = asyncio.create_task(work())
    return dict(_download)
