"""Servidor FastAPI principal do Jefrey (Fase P5).

Monta:
- /approvals (sub-aplicação Starlette com autenticação Bearer e HITL)
- /chat (endpoints de conversação assíncrona com content_guard)
- /memory (busca vetorial e métricas de memória)
- /health (health check para monitoramento e docker-compose)
"""
from __future__ import annotations

import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.jefrey.api.approvals import build_approvals_app
from src.jefrey.api.auth_middleware import FastAPIAuthMiddleware
from src.jefrey.api.chat import router as chat_router
from src.jefrey.api.memory import router as memory_router
from src.jefrey.core.config import get_settings

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

    # CORS para acesso por UIs e frontends locais
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # SECURITY (P6-pre): autenticação Bearer + user context (multi-tenant)
    app.add_middleware(FastAPIAuthMiddleware)

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
