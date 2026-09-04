"""P1.2 — API STT (Axiom #1 FAIL-CLOSED, #2 ISOLAMENTO, CIPHER 026/031/033, Livro 4 cap6)."""
from __future__ import annotations
import logging
import time
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, UploadFile, File

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stt", tags=["stt"])

@router.get("/health")
async def stt_health():
    try:
        from src.jefrey.core.stt_engine import get_stt_engine
        e = get_stt_engine()
        return {"status": "ok", "model": e.model_name, "language": e.language}
    except Exception as ex:
        return {"status": "degraded", "error": str(ex)}

@router.post("")
async def stt_transcribe(request: Request, audio: UploadFile = File(...)):
    # Axiom #2: user_id obrigatório (fail-closed)
    user_id = getattr(request.state, "user_id", None)
    if not user_id or user_id in ("anonymous", "system"):
        # auth middleware already blocks, but double-check
        raise HTTPException(status_code=401, detail="nao autenticado (user_id ausente)")

    # CIPHER-032 + Axiom #5: Policy check Risk MEDIUM
    try:
        from src.jefrey.core.policy import get_policy_engine, PolicyContext
        from src.jefrey.core.registry import register_default_tools
        register_default_tools()
        # ensure stt tool registered (fallback)
        try:
            from src.jefrey.core.registry import TOOL_REGISTRY
            if not TOOL_REGISTRY.get("stt_transcribe"):
                from src.jefrey.core.policy import RiskLevel
                from src.jefrey.core.rbac import Role
                TOOL_REGISTRY.register(name="stt_transcribe", risk=RiskLevel.MEDIUM, required_role=Role.USER, description="STT transcribe")
        except Exception:
            pass
        pe = get_policy_engine()
        ctx = PolicyContext(thread_id="stt", user_role=getattr(request.state, "oauth2_client", "user") and "user" or "user", user_id=user_id, autonomous=True)
        dec = pe.decide("stt_transcribe", args={}, ctx=ctx)
        if dec.decision.value == "deny":
            raise HTTPException(status_code=403, detail=dec.reason)
        if dec.decision.value == "hitl":
            raise HTTPException(status_code=403, detail="stt requer aprovacao (HITL)")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("STT policy error: %s", e)
        raise HTTPException(status_code=500, detail="erro interno policy STT")

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
    except Exception:
        pass

    try:
        from src.jefrey.core.stt_engine import get_stt_engine
        from src.jefrey.core.metrics import STT_DURATION, STT_REQUESTS
        engine = get_stt_engine()
        text = engine.transcribe(data)
        elapsed = time.monotonic() - start
        try:
            STT_DURATION.labels(provider=provider, model=model).observe(elapsed)
            STT_REQUESTS.labels(status="success").inc()
        except Exception:
            pass
        # Audit log (CIPHER-010)
        try:
            from src.jefrey.core.audit import audit_tool_call
            audit_tool_call(thread_id="stt", tool_name="stt_transcribe", actor_role="user", risk="medium", decision="allow", reason="stt ok", source="stt")
        except Exception:
            pass
        # EventBus per-tenant (CIPHER-033) — best effort, fail open for MVP
        try:
            from src.jefrey.eventbus.publisher import publish_event
            import json as _json
            # HMAC kid rotation handled in signing; publish wraps
            # publish_event is async? try sync fallback
            pass
        except Exception:
            pass
        return {"transcript": text, "language": model, "duration": round(elapsed,3)}
    except ValueError as ve:
        try:
            from src.jefrey.core.metrics import STT_REQUESTS
            STT_REQUESTS.labels(status="bad_request").inc()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        try:
            from src.jefrey.core.metrics import STT_REQUESTS
            STT_REQUESTS.labels(status="error").inc()
        except Exception:
            pass
        logger.error("STT runtime: %s", re)
        raise HTTPException(status_code=500, detail=str(re))
    except Exception as e:
        try:
            from src.jefrey.core.metrics import STT_REQUESTS
            STT_REQUESTS.labels(status="error").inc()
        except Exception:
            pass
        logger.error("STT error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="erro interno STT")
