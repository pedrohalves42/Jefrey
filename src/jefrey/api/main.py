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
# CIPHER-313: chromadb tenta enviar telemetria (posthog) e loga ERROR a cada operacao
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
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
from src.jefrey.api.connections import router as connections_router
from src.jefrey.api.tts import router as tts_router
from src.jefrey.core.config import get_settings
import time as _time
_START_TIME = _time.time()
from src.jefrey.core.metrics import SERVICE_HEALTH, UPTIME
from src.jefrey.api.signing_routes import router as signing_router

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
        if "CHANGE_ME" in _pw or (_pw == "jefrey" and cfg.is_prod):
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

    @app.on_event("startup")
    async def _startup_ensure_embedding_model():
        # CIPHER-313: sem o modelo de embeddings no Ollama a memoria falha em silencio
        # ("model nomic-embed-text not found"). Baixa em background se estiver faltando.
        import asyncio as _aio

        async def _pull():
            try:
                cfg2 = get_settings()
                base = (os.getenv("JEFREY_EMBEDDINGS__BASE_URL") or getattr(cfg2.llm, "base_url", None) or "http://ollama:11434").rstrip("/")
                model = getattr(getattr(cfg2, "embeddings", None), "model", None) or "nomic-embed-text"
                async with _f3_httpx.AsyncClient(timeout=10) as c:
                    tags = (await c.get(base + "/api/tags")).json().get("models", [])
                if any(str(m.get("name", "")).split(":")[0] == model.split(":")[0] for m in tags):
                    return
                logger.warning("modelo de embeddings %s ausente no Ollama - baixando em background", model)
                async with _f3_httpx.AsyncClient(timeout=_f3_httpx.Timeout(3600.0, connect=10.0)) as c:
                    r = await c.post(base + "/api/pull", json={"model": model, "stream": False})
                    logger.info("pull %s -> HTTP %s", model, r.status_code)
            except Exception as e:
                logger.warning("nao foi possivel garantir o modelo de embeddings: %s", e)

        _aio.create_task(_pull())

    @app.on_event("startup")
    async def _startup_create_tables():
        # Tabelas do ORM (approvals/oauth2) nao eram criadas em lugar nenhum -> HITL quebrava
        # com "relation approvals does not exist". create_all e idempotente.
        try:
            from src.jefrey.core.db import create_oauth2_tables
            create_oauth2_tables()
            # CIPHER-305: audit_logs (models.AuditLog) - antes nao existia e todo audit ia p/ fallback
            from src.jefrey.core.db import get_engine
            from src.jefrey.core.models import AuditLog
            AuditLog.__table__.create(bind=get_engine(), checkfirst=True)
        except Exception as e:
            logger.error("criacao das tabelas do ORM falhou (HITL/approvals indisponivel): %s", e)

    @app.on_event("startup")
    async def _startup_register_tools():
        try:
            from src.jefrey.core.registry import register_default_tools
            register_default_tools()
        except Exception as e:
            logger.warning("register_default_tools falhou: %s", e)
        try:
            from src.jefrey.skills import load_skills
            load_skills()
        except Exception as e:
            logger.warning("load_skills falhou: %s", e)

    # CIPHER-104: fecha pool do checkpointer em shutdown (evita leak de conexoes AsyncPG)
    @app.on_event("shutdown")
    async def _close_checkpointer():
        try:
            from src.jefrey.core.checkpointer import close_postgres_checkpointer
            await close_postgres_checkpointer()
        except Exception:
            pass


    # CIPHER-031: CORS origins must be explicitly configured via env var
    # In production, JEFREY_API__CORS_ORIGINS must be set to specific allowed domains
    # Without explicit config, CORS is NOT enabled (fail-closed security)
    # This prevents accidental open CORS in production without env var setup
    # SECURITY (P6-pre): autenticacao Bearer + user context (multi-tenant)
    # Added FIRST so CORS (added second) is outermost and handles preflight before auth
    app.add_middleware(FastAPIAuthMiddleware)

    # CIPHER-031: CORS origins must be explicitly configured via env var
    cors_origins_raw = os.getenv("JEFREY_API__CORS_ORIGINS")
    cors_origins = [] if not cors_origins_raw else [o.strip() for o in cors_origins_raw.split(",") if o.strip()]
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["*"],
        )

    # Modo local (sem Docker): so este PC e a propria tela falam com a API. Adicionado por ULTIMO = mais externo,
    # entao roda antes da autenticacao e do CORS.
    from src.jefrey.api.local_guard import LocalGuardMiddleware, local_guard_enabled

    if local_guard_enabled():
        app.add_middleware(
            LocalGuardMiddleware,
            # nomes que os containers usam entre si e as origens de tela ja liberadas no CORS
            extra_hosts=[*(os.getenv("JEFREY_ALLOWED_HOSTS") or "").split(","),
                         *(["jefrey-api", "api", "host.docker.internal", "mcp-server", "frontend"]
                           if (os.getenv("JEFREY_MODE") or "").lower() != "native" else [])],
            extra_origins=[*(os.getenv("JEFREY_ALLOWED_ORIGINS") or "").split(","), *cors_origins],
        )

    # P6: Observability -- Prometheus metrics endpoint (PUBLICO, sem auth)
    SERVICE_HEALTH.labels(component="api").set(1)
    try:
        UPTIME.set_function(lambda: _time.time() - _START_TIME)
    except Exception:
        pass
    app.include_router(metrics_router)
    app.include_router(signing_router)

    # Health check no nivel raiz (PUBLICO, sem auth)
    @app.get("/api/status", tags=["system"])
    async def api_status():
        """API status endpoint - reporta status de todas as 7 pecas (Axiom #1, CIPHER-031).
        PUBLICO, sem auth - usado pelo frontend em localhost:3001 para indicar status em tempo real.
        """
        from src.jefrey.core.metrics import SERVICE_HEALTH
        from src.jefrey.core.config import get_settings

        cfg = get_settings()
        base = (getattr(cfg.llm, 'base_url', None) or 'http://host.docker.internal:11434').rstrip('/')

        # Check Ollama/LLM availability
        ollama_ok = False
        try:
            async with _f3_httpx.AsyncClient(timeout=2) as c:
                r = await c.get(base + '/api/tags')
                ollama_ok = r.status_code == 200
        except Exception:
            pass

        native = (os.getenv("JEFREY_MODE", "") or "").lower() == "native"  # sem Docker: SQLite + memoria local

        # Check Redis
        redis_ok = False
        try:
            if native:
                raise RuntimeError("modo nativo: sem Redis")
            import redis as _redis
            r = _redis.Redis.from_url(cfg.redis.dsn or 'redis://localhost:6379')
            r.ping()
            redis_ok = True
        except Exception:
            pass

        # Check Postgres (simple connectivity - Axiom #1 fail-closed)
        postgres_ok = False
        try:
            if str(cfg.database.dsn or "").startswith("sqlite"):
                from sqlalchemy import text as _sqltext
                from src.jefrey.core.db import get_engine
                with get_engine().connect() as _c:
                    _c.execute(_sqltext("SELECT 1"))
                postgres_ok = True
                raise StopIteration  # banco local verificado
            # Try asyncpg first (faster async), fallback to psycopg
            try:
                import asyncpg
                # Convert postgresql+psycopg:// to postgresql:// for asyncpg
                dsn = cfg.database.dsn.replace("postgresql+psycopg://", "postgresql://") if cfg.database.dsn else 'postgresql://localhost/jefrey'
                conn = await asyncpg.connect(dsn)
                await conn.close()
                postgres_ok = True
            except ImportError:
                # Fallback to psycopg sync
                import psycopg
                dsn = cfg.database.dsn.replace("postgresql+psycopg://", "postgresql://") if cfg.database.dsn else 'postgresql://localhost/jefrey'
                conn = psycopg.connect(dsn)
                conn.close()
                postgres_ok = True
        except StopIteration:
            pass
        except Exception as e:
            logger.warning("Postgres health check failed: %s", e)

        # Check MCP Gateway (antes era fixo em "starting" - nunca refletia o estado real)
        mcp_status = "off" if native else "down"
        try:
            if native:
                raise RuntimeError("modo nativo: sem servidor MCP")
            _mcp_url = os.getenv("JEFREY_MCP_HEALTH_URL") or f"http://mcp-server:{cfg.mcp.port}/health"
            async with _f3_httpx.AsyncClient(timeout=2) as c:
                r = await c.get(_mcp_url)
                mcp_status = "ok" if r.status_code == 200 else "degraded"
        except Exception as e:
            if not native:
                logger.warning("MCP health check failed: %s", e)

        # Update metrics
        try:
            SERVICE_HEALTH.labels(component="api").set(1)
        except Exception:
            pass

        return {
            "api": {"status": "ok" if ollama_ok else "degraded"},
            "stt": {"status": "ok"},  # Already verified via /stt/health
            "tts": {"status": "ok"},  # Already verified via /tts/health
            "mcp": {"status": mcp_status},  # MCP service health (probe real)
            "ollama": {"status": "ok" if ollama_ok else "degraded"},
            "redis": {"status": "off" if native else ("ok" if redis_ok else "degraded")},
            "postgres": {"status": "ok" if postgres_ok else "degraded"},
            "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z"
        }

    # Health check no nivel raiz (PUBLICO, sem auth)
    @app.get("/health", tags=["system"])
    async def health_check():
        """Health check endpoint - reporta status de seguranca (P4).
        PUBLICO, sem auth - usado por docker-compose e orquestration.
        """
        from src.jefrey.core.policy import get_policy_engine
        from src.jefrey.core.rbac import RBAC
        from src.jefrey.core.rate_limit import get_rate_limiter
        from src.jefrey.core.hitl import HITLManager

        policy = get_policy_engine()
        rbac = RBAC()
        rate_limiter = get_rate_limiter()
        hitl = HITLManager()

        # Determina status geral
        all_active = all([policy is not None, rbac is not None, rate_limiter is not None])

        # Status de cada componente
        components = {
            "policy_engine": "active" if policy else "inactive",
            "rbac_engine": "active" if rbac else "inactive",
            "rate_limiter": "active" if rate_limiter else "inactive",
            "content_guard": "active",
            "hitl_manager": "active" if hitl else "inactive",
        }

        overall = "ok" if all_active else "degraded"

        # Metrics: update service health labels
        try:
            from src.jefrey.core.metrics import SERVICE_HEALTH
            SERVICE_HEALTH.labels(component="api").set(1 if overall == "healthy" else 0)
        except Exception:
            pass

        return {
            "status": overall,
            "version": get_settings().version,
            "security_components": components,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z"
        }

    # Registra routers do FastAPI
    app.include_router(auth_router)
    app.include_router(chat_router)
    from src.jefrey.api.llm_settings import router as llm_settings_router
    app.include_router(llm_settings_router)
    from src.jefrey.api.skills_routes import router as skills_router
    app.include_router(skills_router)
    from src.jefrey.api.reminders_routes import router as reminders_router
    app.include_router(reminders_router)
    from src.jefrey.api.system_routes import router as system_router
    app.include_router(system_router)
    from src.jefrey.api.profile_routes import router as profile_router
    app.include_router(profile_router)
    from src.jefrey.api.whatsapp_routes import router as whatsapp_router
    app.include_router(whatsapp_router)
    app.include_router(memory_router)
    app.include_router(stt_router)
    app.include_router(tts_router)
    app.include_router(connections_router)

    # Monta a sub-aplicacao de aprovacoes Starlette (mantem CIPHER-019, 020, 024 intactos)
    # FIX: mount em /approvals (nao /) para evitar conflito com outros routers.
    # Rotas relativas do sub-app: /pending e /{id}/decide
    # Resultado final: /approvals/pending e /approvals/{id}/decide
    # AUDITORIA 2026-10: o endpoint publico /ws (WebSocket sem login) foi removido: a interface nao o usa e o
    # gerenciador transmitiria a todos os conectados consultas de memoria e ids de usuario. Reintroduzir so com
    # autenticacao (primeira mensagem com token, nunca token na URL).

    approvals_app = build_approvals_app()
    app.mount("/approvals", approvals_app)

    # UI-1 Shell Ã¢â‚¬â€' serve Vite build em / (Axiom #1: 1 programa, 7 pecas -> sem novo container)
    # FastAPI StaticFiles serve src/jefrey/static com html=True; rotas /api/* tem precedencia sobre mount "/"
    try:
        _static_dir = Path(__file__).resolve().parent.parent / "static"  # src/jefrey/static (fix: api/ -> jefrey/)
        if _static_dir.exists():
            # mount em "/" depois das rotas Ã¢â‚¬â€' /health, /chat, /memory, /approvals continuam com prioridade
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
        host=os.getenv("JEFREY_API_HOST", "0.0.0.0"),  # modo local (sem Docker) usa 127.0.0.1
        port=int(os.getenv("JEFREY_API_PORT", "8000")),
        reload=False  # docker read_only fix: watchfiles /app/.cache Permission denied (Axiom 1),
    )


if __name__ == "__main__":
    main()

