"""Voz natural na nuvem (opcional): so existe se o ChatGPT estiver conectado como cerebro."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.jefrey.core import cloudvoice as CV

router = APIRouter(prefix="/voice/cloud", tags=["voice"])


def _login(request: Request) -> None:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")


class SpeakBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


@router.get("")
async def status(request: Request):
    _login(request)
    return {"available": CV.available()}


@router.post("/speak")
async def speak(request: Request, body: SpeakBody):
    _login(request)
    try:
        audio = await CV.synth(body.text)
    except CV.CloudVoiceError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})
