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
from fastapi.middleware.cors import CORSMiddleware

from src.jefrey.api.approvals import build_approvals_app
from src.jefrey.api.auth_middleware import FastAPIAuthMiddleware
from src.jefrey.api.chat import router as chat_router
from src.jefrey.api.memory import router as memory_router
from src.jefrey.api.metrics_endpoint import router as metrics_router
from src.jefrey.core.config import get_settings
from src.jefrey.core.metrics import SERVICE_HEALTH

logger = logging.getLogger(__name__)

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
        except Exception:
            _ok = False
        CONFIG_VALID.set(1 if _ok else 0)
    except Exception:
        pass

    app = FastAPI(
        title="Jefrey API",
        version=cfg.version,
        description="API REST unificada do assistente Jefrey (FastAPI + Starlette)",
    )

    # SECURITY (P0.5): CORS restrito -- origins configuraveis via env
    # Em producao, JEFREY_API__CORS_ORIGINS deve listar os dominios permitidos.
    cors_origins_raw = os.getenv("JEFREY_API__CORS_ORIGINS", "")
    if cors_origins_raw:
        cors_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]
    else:
        # Default: apenas localhost (desenvolvimento)
        cors_origins = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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
    app.include_router(chat_router)
    app.include_router(memory_router)

    # Monta a sub-aplicacao de aprovacoes Starlette (mantem CIPHER-019, 020, 024 intactos)
    # FIX: mount em /approvals (nao /) para evitar conflito com outros routers.
    # Rotas relativas do sub-app: /pending e /{id}/decide
    # Resultado final: /approvals/pending e /approvals/{id}/decide
    approvals_app = build_approvals_app()
    app.mount("/approvals", approvals_app)

    return app

app = create_app()

def main():
    """Ponto de entrada para execucao via CLI ou container."""
    cfg = get_settings()
    uvicorn.run(
        "src.jefrey.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=cfg.debug,
    )

if __name__ == "__main__":
    main()
