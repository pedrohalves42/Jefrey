"""Servidor FastAPI principal do Jefrey (Fase P5).

Monta:
- /approvals (sub-aplicação Starlette com autenticação Bearer e HITL)
- /chat (endpoints de conversação assíncrona com content_guard)
- /memory (busca vetorial e métricas de memória)
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
    # SECURITY (P6-pre): valida configurações de produção no startup
    cfg = get_settings()
    for warning in cfg.api.validate_for_production():
        logger.warning(warning)
        print(warning)

    app = FastAPI(
        title="Jefrey API",
        version=cfg.version,
        description="API REST unificada do assistente Jefrey (FastAPI + Starlette)",
    )

    # SECURITY (P0.5): CORS restrito — origins configuráveis via env
    # Em produção, JEFREY_API__CORS_ORIGINS deve listar os domínios permitidos.
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

    # SECURITY (P6-pre): autenticação Bearer + user context (multi-tenant)
    app.add_middleware(FastAPIAuthMiddleware)

    # P6: Observability — Prometheus metrics endpoint
    SERVICE_HEALTH.labels(component="api").set(1)
    app.include_router(metrics_router)

    # Health check no nível raiz
    @app.get("/health", tags=["system"])
    async def health():
        return {"status": "ok", "version": get_settings().version}

    # Registra routers do FastAPI
    app.include_router(chat_router)
    app.include_router(memory_router)

    # Monta a sub-aplicação de aprovações Starlette (mantém CIPHER-019, 020, 024 intactos)
    # A sub-aplicação possui suas próprias rotas /approvals/pending e /approvals/{id}/decide
    approvals_app = build_approvals_app()
    app.mount("/", approvals_app)

    return app

app = create_app()

def main():
    """Ponto de entrada para execução via CLI ou container."""
    cfg = get_settings()
    uvicorn.run(
        "src.jefrey.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=cfg.debug,
    )

if __name__ == "__main__":
    main()
