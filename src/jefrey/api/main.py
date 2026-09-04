"""Servidor FastAPI principal do Jefrey (Fase P5).

Monta:
- /approvals (sub-aplicacao Starlette com autenticacao Bearer e HITL)
- /chat (endpoints de conversacao assincrona com content_guard)
- /memory (busca vetorial e metricas de memoria)
- /health (health check para monitoramento e docker-compose)
"""
from __future__ import annotations

import logging
import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware

from src.jefrey.api.approvals import build_approvals_app
from src.jefrey.api.auth_middleware import FastAPIAuthMiddleware
from src.jefrey.api.auth import router as auth_router
from src.jefrey.api.chat import router as chat_router
from src.jefrey.api.memory import router as memory_router
from src.jefrey.api.metrics_endpoint import router as metrics_router
from src.jefrey.api.stt import router as stt_router
from src.jefrey.api.tts import router as tts_router
from src.jefrey.core.config import get_settings
from src.jefrey.core.metrics import SERVICE_HEALTH

logger = logging.getLogger(__name__)

# F3 LLM probe fail-closed visible (Axiom #1, DDIA cap12) - never crash, lazy (HPP)
import httpx as _f3_httpx
_f3_log2 = __import__("logging").getLogger(__name__)
async def _f3_llm_probe():
    try:
        from src.jefrey.core.config import get_settings
        cfg = get_settings()
        base = (getattr(cfg.llm, 'base_url', None) or 'http://host.docker.internal:11434').rstrip('/')
        url = base + '/api/tags'
        async with _f3_httpx.AsyncClient(timeout=2) as c:
            r = await c.get(url)
            ok = r.status_code == 200
            has_qwen = 'qwen2' in r.text if ok else False
            _f3_log2.info(f'LLM probe base_url={base} model={getattr(cfg.llm,"model","?")} reachable={ok} has_qwen2={has_qwen} status={r.status_code}')
            if not ok:
                _f3_log2.warning('LLM offline - modo mock visivel na UI (Axiom #1 fail-closed)')
    except Exception as e:
        try:
            _f3_log2.warning(f'LLM probe falhou: {e} - modo mock')
        except:
            pass


def create_app() -> FastAPI:
    # SECURITY (P6-pre): validacao de producao no startup
    cfg = get_settings()
    for warning in cfg.api.validate_for_production():
        logger.warning(warning)
        print(warning)
    # N2 AXIOM observabilidade: CONFIG_VALID gauge mirror verify_env (CIPHER-019/002/001)
    try:
        from src.jefrey.core.metrics import CONFIG_VALID
        _sk = cfg.api.secret_key or ""
        _pw = cfg.database.password or ""
        _ok = True
        if "CHANGE_ME" in _sk or not _sk or len(_sk) < 32:
            _ok = False
        if "CHANGE_ME" in _pw or (_pw == "jefrey" and not cfg.debug):
            _ok = False
        if cfg.mcp.service_role not in cfg.mcp.allowed_roles:
            _ok = False
        try:
            _ = cfg.database.dsn
            _ = cfg.redis.dsn
        except Exception as e:
            logger.warning("CONFIG_VALID DSN check falhou: %s", e)
            _ok = False
        CONFIG_VALID.set(1 if _ok else 0)
    except Exception as e:
        logger.warning("CONFIG_VALID check falhou (observabilidade): %s", e)

    app = FastAPI(
        title="Jefrey API",
        version=cfg.version,
        description="API REST unificada do assistente Jefrey (FastAPI + Starlette)",
    )

    # F3 startup probe (Axiom #1 visible, never crash)
    @app.on_event("startup")
    async def _f3_startup_llm_probe():
        await _f3_llm_probe()


    # CIPHER-031: CORS origins must be explicitly configured via env var
    # In production, JEFREY_API__CORS_ORIGINS must be set to specific allowed domains
    # Without explicit config, CORS is NOT enabled (fail-closed security)
    # This prevents accidental open CORS in production without env var setup
    cors_origins_raw = os.getenv("JEFREY_API__CORS_ORIGINS")
    cors_origins = [] if not cors_origins_raw else [o.strip() for o in cors_origins_raw.split(",") if o.strip()]
    
    # Only add CORS middleware if origins are explicitly configured
    # Fail-closed: no CORS env var = no CORS middleware added
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-User-Id"],
        )

    # SECURITY (P6-pre): autenticacao Bearer + user context (multi-tenant)
    app.add_middleware(FastAPIAuthMiddleware)

    # P6: Observability -- Prometheus metrics endpoint (PUBLICO, sem auth)
    SERVICE_HEALTH.labels(component="api").set(1)
    app.include_router(metrics_router)

    # Health check no nivel raiz (PUBLICO, sem auth)
    @app.get("/health", tags=["system"])
    async def health():
        return {"status": "ok", "version": get_settings().version}

    # Registra routers do FastAPI
    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(memory_router)
    app.include_router(stt_router)
    app.include_router(tts_router)

    # Monta a sub-aplicacao de aprovacoes Starlette (mantem CIPHER-019, 020, 024 intactos)
    # FIX: mount em /approvals (nao /) para evitar conflito com outros routers.
    # Rotas relativas do sub-app: /pending e /{id}/decide
    # Resultado final: /approvals/pending e /approvals/{id}/decide
    approvals_app = build_approvals_app()
    app.mount("/approvals", approvals_app)

    # UI-1 Shell — serve Vite build em / (Axiom #1: 1 programa, 7 pecas -> sem novo container)
    # FastAPI StaticFiles serve src/jefrey/static com html=True; rotas /api/* tem precedencia sobre mount "/"
    try:
        _static_dir = Path(__file__).resolve().parent.parent / "static"  # src/jefrey/static (fix: api/ -> jefrey/)
        if _static_dir.exists():
            # mount em "/" depois das rotas — /health, /chat, /memory, /approvals continuam com prioridade
            app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="ui-static")
            logger.info("UI static mounted at / from %s", _static_dir)
    except Exception as e:
        logger.warning("UI static mount falhou: %s", e)

    return app

app = create_app()

def main():
    """Ponto de entrada para execucao via CLI ou container."""
    cfg = get_settings()
    uvicorn.run(
        "src.jefrey.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False  # docker read_only fix: watchfiles /app/.cache Permission denied (Axiom 1),
    )

if __name__ == "__main__":
    main()