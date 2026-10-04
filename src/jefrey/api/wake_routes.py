"""Atalho global e palavra de ativacao."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from src.jefrey.core import wake, wakeword

logger = logging.getLogger(__name__)
router = APIRouter(tags=["wake"])
MAX_WAKE_BYTES = 1_500_000  # uma fala curta; o resto e recusado


def _user(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    return str(uid)


@router.get("/system/wake")
async def wake_poll(request: Request):
    """A tela pergunta se o atalho global foi apertado (True uma vez por aperto)."""
    _user(request)
    return {"wake": wake.poll()}


@router.post("/stt/wake")
async def wake_check(request: Request, audio: UploadFile = File(...)):
    """Transcreve (localmente) uma fala curta e diz se ela comeca chamando o Jefrey.

    Devolve SO {wake, rest}: o que nao for para o Jefrey nunca sai daqui e o audio nao e guardado.
    """
    _user(request)
    from src.jefrey.core import voice_ready

    if not voice_ready.status()["ready"]:
        return {"wake": False, "rest": "", "ready": False}
    data = await audio.read(MAX_WAKE_BYTES + 1)
    if len(data) < 100 or len(data) > MAX_WAKE_BYTES:
        return {"wake": False, "rest": "", "ready": True}
    try:
        from src.jefrey.core.stt_engine import get_stt_engine

        engine = await asyncio.to_thread(get_stt_engine)
        try:
            text = await asyncio.to_thread(engine.transcribe, data, "Jefrey, assistente pessoal.")
        except TypeError:  # motor sem "dica" de vocabulario
            text = await asyncio.to_thread(engine.transcribe, data)
    except ValueError:  # silencio ou ruido
        return {"wake": False, "rest": "", "ready": True}
    except Exception as e:
        logger.warning("palavra de ativacao: transcricao falhou (%s)", type(e).__name__)
        return {"wake": False, "rest": "", "ready": True}
    rest = wakeword.find_wake(text)
    if rest is None:
        return {"wake": False, "rest": "", "ready": True}
    return {"wake": True, "rest": rest[:500], "ready": True}
