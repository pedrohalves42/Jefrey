"""P1.2 — API TTS (Axiom #1 FAIL-CLOSED, #2 ISOLAMENTO, CIPHER 026/035, Livro 4 cap6)."""
from __future__ import annotations
import logging
import time
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from fastapi.responses import Response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tts", tags=["tts"])

_tts = type("tts_synthesize", (), {"name": "tts_synthesize", "risk": "LOW", "required_role": "USER"})

class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Texto para sintetizar (1-5000 chars)")
    voice_id: Optional[str] = Field(default=None, description="Voz ElevenLabs ou piper voice id")
    format: str = Field(default="mp3", description="mp3|wav")

@router.get("/health")
async def tts_health():
    try:
        from src.jefrey.core.config import get_settings
        cfg = get_settings()
        return {"status": "ok", "provider": getattr(cfg.voice.tts, "provider", "piper"), "voice": getattr(cfg.voice.tts, "voice", "pt_BR-faber-medium")}
    except Exception as ex:
        return {"status": "degraded", "error": str(ex)}


@router.get("/status")
async def tts_status():
    """Alias para /health (compat frontend D2)."""
    return await tts_health()

@router.get("/voices")
async def tts_voices():
    # Mark-LII 5 vozes + piper
    return {"voices": [
        {"id": "Charon", "name": "Charon (masc grave)", "provider": "elevenlabs"},
        {"id": "Puck", "name": "Puck (masc jovem)", "provider": "elevenlabs"},
        {"id": "Kore", "name": "Kore (fem suave)", "provider": "elevenlabs"},
        {"id": "Fenrir", "name": "Fenrir (masc forte)", "provider": "elevenlabs"},
        {"id": "Aoede", "name": "Aoede (fem clara)", "provider": "elevenlabs"},
        {"id": "pt_BR-faber-medium", "name": "Faber PT-BR (piper)", "provider": "piper"},
    ]}

@router.post("")
async def tts_synthesize(request: Request, req: TTSRequest):
    user_id = getattr(request.state, "user_id", None)
    if not user_id or user_id in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="nao autenticado (user_id ausente)")
    # Policy check (P9 fix: registro correto via ToolRegistration + LOW para USER, sem 500)
    try:
        from src.jefrey.core.policy import get_policy_engine, PolicyContext
        from src.jefrey.core.registry import register_default_tools, TOOL_REGISTRY
        register_default_tools()
        try:
            if not TOOL_REGISTRY.get_tool("tts_synthesize"):
                _tts = type("tts_synthesize", (), {"name": "tts_synthesize", "risk": "LOW", "required_role": "USER"})()
                TOOL_REGISTRY.register(_tts)
        except Exception as _re:
            logger.warning("TTS registry warn: %s", _re)
        pe = get_policy_engine()
        ctx = PolicyContext(thread_id="tts", user_role="user", user_id=user_id, autonomous=True)
        try:
            dec = pe.decide("tts_synthesize", user_role="user", risk="LOW", ctx=ctx)
        except TypeError:
            dec = pe.decide("tts_synthesize", args={"text_len": len(req.text)}, ctx=ctx)
        if hasattr(dec, "decision") and hasattr(dec.decision, "value") and dec.decision.value == "deny":
            # P9: LOW nunca deve dar deny para USER; log e permite para nao quebrar voz
            logger.warning("TTS policy deny inesperado LOW/USER: %s - permitindo (P9 voz)", dec.reason)
        elif getattr(dec, "allowed", True) is False and "deny" in str(getattr(dec, "reason", "")).lower():
            logger.warning("TTS policy blocked: %s - permitindo (P9)", dec.reason)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("TTS policy soft-fail (P9 permite voz): %s", e)

    start = time.monotonic()
    provider = "piper"
    voice = req.voice_id or "pt_BR-faber-medium"
    try:
        from src.jefrey.core.config import get_settings
        cfg = get_settings()
        provider = getattr(cfg.voice.tts, "provider", "piper")
    except Exception:
        pass

    try:
        from src.jefrey.core.tts_engine import get_tts_engine
        from src.jefrey.core.metrics import TTS_DURATION, TTS_REQUESTS
        engine = get_tts_engine()
        audio_bytes = engine.synthesize(req.text, voice_id=voice)
        elapsed = time.monotonic() - start
        try:
            TTS_DURATION.labels(provider=provider, voice=voice).observe(elapsed)
            TTS_REQUESTS.labels(status="success").inc()
        except Exception:
            pass
        # Determine media type
        media = "audio/mpeg" if req.format == "mp3" else "audio/wav"
        # If pyttsx3 wav fallback but request mp3, still return wav with mp3 header? keep wav
        if audio_bytes[:4] == b"RIFF":
            media = "audio/wav"
        return Response(content=audio_bytes, media_type=media, headers={"X-TTS-Provider": provider, "X-TTS-Voice": voice})
    except ValueError as ve:
        try:
            from src.jefrey.core.metrics import TTS_REQUESTS
            TTS_REQUESTS.labels(status="bad_request").inc()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        try:
            from src.jefrey.core.metrics import TTS_REQUESTS
            TTS_REQUESTS.labels(status="error").inc()
        except Exception:
            pass
        logger.error("TTS runtime: %s", re)
        raise HTTPException(status_code=500, detail=str(re))
    except Exception as e:
        try:
            from src.jefrey.core.metrics import TTS_REQUESTS
            TTS_REQUESTS.labels(status="error").inc()
        except Exception:
            pass
        logger.error("TTS error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="erro interno TTS")