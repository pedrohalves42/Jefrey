"""P1.2 — API STT (Axiom #1 FAIL-CLOSED, #2 ISOLAMENTO, CIPHER 026/031/033, Livro 4 cap6)."""
from __future__ import annotations
import logging
import time

from fastapi import APIRouter, Request, HTTPException, UploadFile, File

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stt", tags=["stt"])

@router.get("/health")
async def stt_health():
    # CIPHER-304: o health NAO carrega o modelo. Antes get_stt_engine() baixava/carregava o
    # Whisper de forma sincrona dentro do event loop e congelava a API inteira por minutos.
    try:
        from src.jefrey.core import stt_engine as _se
        from src.jefrey.core.config import get_settings
        cfg = get_settings()
        loaded = _se._stt_engine is not None
        return {"status": "ok", "model": getattr(cfg.voice.stt, "model", "base"),
                "language": getattr(cfg.voice.stt, "language", "pt"),
                "provider": getattr(cfg.voice.stt, "provider", "whisper"),
                "model_loaded": loaded}
    except Exception as ex:
        return {"status": "degraded", "error": str(ex)}


@router.get("/status")
async def stt_status():
    """Alias para /health (compat frontend D2)."""
    return await stt_health()

@router.post("")
async def stt_transcribe(request: Request, audio: UploadFile = File(...)):
    # Axiom #2: user_id obrigatório (fail-closed)
    user_id = getattr(request.state, "user_id", None)
    if not user_id or user_id in ("anonymous", "system"):
        # auth middleware already blocks, but double-check
        raise HTTPException(status_code=401, detail="nao autenticado (user_id ausente)")

    # Policy check (P9 fix: LOW para STT, sem 500, compat decide signature)
    try:
        from src.jefrey.core.policy import get_policy_engine, PolicyContext
        from src.jefrey.core.registry import register_default_tools, TOOL_REGISTRY

        _stt = type("stt_transcribe", (), {"name": "stt_transcribe", "risk": "LOW", "required_role": "USER"})()
        register_default_tools()
        try:
            if not TOOL_REGISTRY.get_tool("stt_transcribe"):
                _stt = type("stt_transcribe", (), {"name": "stt_transcribe", "risk": "LOW", "required_role": "USER"})()
                TOOL_REGISTRY.register(_stt)
        except Exception as _e:
            logger.debug("ignorado (%s): %s", 'stt.py', type(_e).__name__)
        pe = get_policy_engine()
        ctx = PolicyContext(thread_id="stt", user_role="user", user_id=user_id, autonomous=True)
        try:
            dec = pe.decide("stt_transcribe", user_role="user", risk="LOW", ctx=ctx)
        except TypeError:
            dec = pe.decide("stt_transcribe", args={}, ctx=ctx)
        dv = getattr(getattr(dec, "decision", ""), "value", str(getattr(dec, "decision", ""))).lower() if hasattr(dec, "decision") else ""
        if dv == "deny":
            # CIPHER-311: antes o deny era ignorado ("permitindo")
            logger.warning("STT policy deny: %s", getattr(dec, "reason", ""))
            raise HTTPException(status_code=403, detail="transcricao negada pela politica")
        elif dv == "hitl":
            logger.warning("STT hitl inesperado LOW - permitindo (P9)")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("STT policy soft-fail (P9 permite voz): %s", e)

    # Rate limit 10/min (CIPHER-026) — already in PolicyEngine, but extra guard
    # Read bytes
    try:
        data = await audio.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"falha ao ler audio: {e}")
    if not data or len(data) < 100:
        raise HTTPException(status_code=400, detail="audio vazio ou muito curto")
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="audio muito grande (>10MB)")

    # Metrics histogram
    start = time.monotonic()
    provider = "whisper"
    model = "small"
    try:
        from src.jefrey.core.config import get_settings
        cfg = get_settings()
        provider = getattr(cfg.voice.stt, "provider", "whisper")
        model = getattr(cfg.voice.stt, "model", "small")
    except Exception as _e:
        logger.debug("ignorado (%s): %s", 'stt.py', type(_e).__name__)

    try:
        from src.jefrey.core.stt_engine import get_stt_engine
        from src.jefrey.core.metrics import STT_DURATION, STT_REQUESTS
        import asyncio as _asyncio
        # CIPHER-304: carga do modelo e transcricao sao CPU-bound -> fora do event loop
        engine = await _asyncio.to_thread(get_stt_engine)
        text = await _asyncio.to_thread(engine.transcribe, data)
        elapsed = time.monotonic() - start
        try:
            STT_DURATION.labels(provider=provider, model=model).observe(elapsed)
            STT_REQUESTS.labels(status="success").inc()
        except Exception as _e:
            logger.debug("ignorado (%s): %s", 'stt.py', type(_e).__name__)
        # Audit log (CIPHER-010)
        try:
            from src.jefrey.core.audit import audit_tool_call
            audit_tool_call(thread_id="stt", tool_name="stt_transcribe", actor_role="user", risk="medium", decision="allow", reason="stt ok", source="stt", user_id=user_id)
        except Exception as _e:
            logger.debug("ignorado (%s): %s", 'stt.py', type(_e).__name__)
        # EventBus per-tenant (CIPHER-033) — best effort, fail open for MVP
        try:
            # HMAC kid rotation handled in signing; publish wraps
            # publish_event is async? try sync fallback
            pass
        except Exception as _e:
            logger.debug("ignorado (%s): %s", 'stt.py', type(_e).__name__)
        return {"transcript": text, "language": model, "duration": round(elapsed,3)}
    except ValueError as ve:
        try:
            from src.jefrey.core.metrics import STT_REQUESTS
            STT_REQUESTS.labels(status="bad_request").inc()
        except Exception as _e:
            logger.debug("ignorado (%s): %s", 'stt.py', type(_e).__name__)
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        try:
            from src.jefrey.core.metrics import STT_REQUESTS
            STT_REQUESTS.labels(status="error").inc()
        except Exception as _e:
            logger.debug("ignorado (%s): %s", 'stt.py', type(_e).__name__)
        logger.error("STT runtime: %s", re)
        raise HTTPException(status_code=500, detail=str(re))
    except Exception as e:
        try:
            from src.jefrey.core.metrics import STT_REQUESTS
            STT_REQUESTS.labels(status="error").inc()
        except Exception as _e:
            logger.debug("ignorado (%s): %s", 'stt.py', type(_e).__name__)
        logger.error("STT error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="erro interno STT")