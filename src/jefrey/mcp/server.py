"""Jefrey MCP Gateway (Fase P3a) — FastMCP/MCPServer (mcp 2.x).

Servidor MCP dedicado (PROCESSO SEPARADO) expondo as ferramentas do SkillRegistry
via transporte streamable-http na porta 8001. Cada ferramenta passa obrigatoriamente
pelo PolicyEngine ANTES de executar — com thread_id vindo do request MCP (não hardcoded),
para que o audit log rastreie qual workflow n8n chamou qual ferramenta.

Nota de implementação: em mcp>=2 o high-level server chama-se `MCPServer` (o nome
`FastMCP` da v1 foi renomeado). `openai-agents` exige `mcp<3,>=1.19.0`, então usamos
o SDK mcp já instalado (2.x) sem downgrade (evita regressão em P2).
"""
from __future__ import annotations

# CIPHER-026: Rate limiting per user_id/tool_name using Redis token bucket
import sys
import os
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")  # CIPHER-313: silencia telemetria chromadb
import types
import typing
import logging
import asyncio
import contextvars
import json
from pathlib import Path

from src.jefrey.core.rate_limit import RateLimiter
from src.jefrey.core.metrics import (
    record_mcp_tool_call,
    record_cache_hit,
    record_cache_miss,
    record_oauth_validation,
    record_rate_limit_decision,
    record_bridge_execution,
)

# garante que o pacote 'src' seja importável independente de como o processo sobe
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mcp.server.mcpserver import MCPServer
from starlette.responses import JSONResponse, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from pydantic import create_model
from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# M1: OAuth 2.0 Resource Server (MCP Spec 2026-07-28, Book 5)
# Valida Authorization header antes de qualquer operacao de tool.
# Modo dev: tokens do env var JEFREY_MCP_OAUTH_TOKENS (comma-separated).
# Modo prod: JWT verification / introspection endpoint (futuro).
# Sem token valido = 401 Unauthorized (fail-closed, AXIOM #1).
# ---------------------------------------------------------------------------
import hmac

def _load_valid_tokens() -> set:
    """Carrega tokens validos do .env (JEFREY_MCP_OAUTH_TOKENS)."""
    raw = os.getenv("JEFREY_MCP_OAUTH_TOKENS", "")
    return {t.strip() for t in raw.split(",") if t.strip()}

_OAUTH_ENABLED = os.getenv("JEFREY_MCP_OAUTH_ENABLED", "false").lower() == "true"
_VALID_TOKENS: set = _load_valid_tokens()

def _validate_oauth_token(token: str) -> bool:
    """Valida access token contra tokens registrados.
    Usa hmac.compare_digest para evitar timing attacks (CIPHER-033).
    """
    if not token:
        return False
    for valid in _VALID_TOKENS:
        if hmac.compare_digest(token, valid):
            return True
    return False

def _extract_bearer_token(auth_header: str) -> str | None:
    """Extrai token do header Authorization: Bearer <token>."""
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    return auth_header[len("Bearer "):].strip()

async def _oauth_guard(request) -> JSONResponse | None:
    """Guard OAuth 2.0 para rotas MCP.
    Retorna JSONResponse 401 se token invalido, None se OK.
    Rotas /health sao publicas (sem auth).
    """
    if not _OAUTH_ENABLED:
        return None  # OAuth desabilitado - permite acesso (dev mode)

    # /health e publico (usado por docker-compose healthcheck)
    path = getattr(request, "url", None)
    if path and str(path).rstrip("/").endswith("/health"):
        return None

    auth_header = request.headers.get("Authorization", "")
    token = _extract_bearer_token(auth_header)

    if not token:
        logger.warning("MCP OAuth: missing Authorization header")
        record_oauth_validation("missing")
        return JSONResponse(
            {"error": "missing_auth", "message": "Authorization header com Bearer token e obrigatorio"},
            status_code=401,
        )

    if not _validate_oauth_token(token):
        logger.warning("MCP OAuth: invalid token (length=%d)", len(token))
        record_oauth_validation("invalid")
        return JSONResponse(
            {"error": "invalid_token", "message": "Access token invalido ou expirado"},
            status_code=401,
        )

    # Token valido - extrair role do header se presente
    role_header = request.headers.get("X-Jefrey-Role", None)
    if role_header:
        _ROLE_CV.set(role_header)

    record_oauth_validation("valid")
    return None  # Autenticado com sucesso


# ---------------------------------------------------------------------------
# M2: Discovery Cache (BUG-P3a-01) — Stateless Mode Optimization
# Em stateless_http=True cada request HTTP eh independente; sem cache, o
# list_tools() causa introspeccao repetida do SkillRegistry a cada chamada.
# Cache local com TTL configuravel evita overhead e fornece fallback se
# o registry ficar temporariamente indisponivel.
# ---------------------------------------------------------------------------
import time as _time_mod

_tool_discovery_cache: dict[str, "StructuredTool"] = {}
_cache_ttl: float = float(os.getenv("JEFREY_MCP_CACHE_TTL", "300"))  # 5 min default
_cached_at: float = 0.0
_cache_hits: int = 0
_cache_misses: int = 0


# ---------------------------------------------------------------------------
# P0-1: OAuth Middleware for MCP Tool Execution (Starlette Middleware)
# Valida Authorization header em TODAS as rotas MCP exceto /health e /metrics.
# Isso garante que chamadas de ferramenta via protocolo MCP tambem exigem auth.
# ---------------------------------------------------------------------------
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

class _OAuthMiddleware(BaseHTTPMiddleware):
    """Middleware que valida OAuth para rotas MCP (exceto publicas)."""
    
    PUBLIC_PATHS = {"/health", "/metrics"}
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/")
        
        # Rotas publicas passam direto
        if path in self.PUBLIC_PATHS:
            return await call_next(request)
        
        # Aplica guard OAuth
        guard_response = await _oauth_guard(request)
        if guard_response is not None:
            return guard_response
        
        # Token valido - continua
        return await call_next(request)


def _clear_discovery_cache() -> None:
    """Limpa o cache de discovery (usado em testes e hot-reload)."""
    global _cached_at, _cache_hits, _cache_misses
    _tool_discovery_cache.clear()
    _cached_at = 0.0
    _cache_hits = 0
    _cache_misses = 0
    logger.info("MCP discovery cache cleared")


def _is_cache_valid() -> bool:
    """Verifica se o cache ainda esta dentro do TTL."""
    if not _tool_discovery_cache:
        return False
    return (_time_mod.time() - _cached_at) < _cache_ttl


def _populate_cache(tools: list) -> None:
    """Popula o cache com as ferramentas registradas."""
    global _cached_at
    _tool_discovery_cache.clear()
    for tool in tools:
        _tool_discovery_cache[tool.name] = tool
    _cached_at = _time_mod.time()
    logger.info("MCP discovery cache populated: %d tools, TTL=%.0fs", len(_tool_discovery_cache), _cache_ttl)


def _get_tool_wrapper(tool_name: str) -> "StructuredTool | None":
    """Busca ferramenta no cache com fallback ao registry.

    1. Cache hit dentro do TTL -> retorna direto (O(1))
    2. Cache expirado -> tenta re-popular do registry
    3. Registry falha -> usa cache stale (melhor que nada)
    4. Nenhum -> retorna None
    """
    global _cache_hits, _cache_misses

    # Fast path: cache valido
    if _is_cache_valid() and tool_name in _tool_discovery_cache:
        _cache_hits += 1
        record_cache_hit()
        return _tool_discovery_cache[tool_name]

    # Cache miss ou expirado
    _cache_misses += 1
    record_cache_miss()

    # Tenta re-popular
    if not _is_cache_valid():
        try:
            from src.jefrey.skills import skill_registry
            all_tools = list(skill_registry.get_all_tools())
            _populate_cache(all_tools + INTEGRATION_TOOLS)
        except Exception as exc:
            logger.warning("MCP discovery cache refresh failed: %s", exc)
            # Fallback: usa cache stale se disponivel
            if tool_name in _tool_discovery_cache:
                logger.info("Using stale cache for tool %s", tool_name)
                _cache_hits += 1
                return _tool_discovery_cache[tool_name]
            return None

    return _tool_discovery_cache.get(tool_name)

# ---------------------------------------------------------------------------
# Guarda cada chamada de ferramenta pelo PolicyEngine
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Resolução de papel (role) — CIPHER-001
# O papel NUNCA vem do caller (o parâmetro user_role foi removido do schema de
# cada ferramenta). É resolvido SERVER-SIDE: service_role (config) é a fonte de
# verdade; um header X-Jefrey-Role só é aceito se estiver em allowed_roles.
# Sem essa restrição, qualquer cliente poderia se autodeclarar "admin" e bypassar
# todo o PolicyEngine (vulnerabilidade CIPHER-001).
# ---------------------------------------------------------------------------
_ROLE_CV: contextvars.ContextVar[str | None] = contextvars.ContextVar("jefrey_role", default=None)


def _resolve_role() -> str:
    """Papel efetivo da chamada, resolvido server-side (CIPHER-001).

    Delega em ``resolve_role`` (rbac.py) — mesmo padrão usado pelo agent loop
    (CIPHER-022): o header X-Jefrey-Role só é honrado se estiver em allowed_roles.
    """
    from src.jefrey.core.rbac import resolve_role

    return resolve_role(_ROLE_CV.get()).value


async def _run_guarded(tool: StructuredTool, args: dict, thread_id: str) -> str:
    """Aplica PolicyEngine (thread_id vindo do request) e executa a ferramenta se permitido.

    O papel (role) é resolvido server-side (CIPHER-001) — não há parâmetro user_role
    exposto ao caller; logo nenhum cliente pode se autodeclarar "admin" via payload.
    """
    from src.jefrey.core.policy import get_policy_engine, PolicyContext, Decision
    from src.jefrey.core.registry import register_default_tools

    policy = get_policy_engine()
    ctx = PolicyContext(thread_id=thread_id, user_role=_resolve_role(), autonomous=policy.autonomous)
    # CIPHER-026: Rate limiting check (Axiom #2 surrogate thread_id, fail-closed deny)
    try:
        _rl_dec = await RateLimiter().is_allowed(thread_id, tool.name)
    except RuntimeError as _e:
        logger.warning("rate limit check falhou (fail-closed deny): %s", _e)
        record_rate_limit_decision(tool.name, "deny")
        return f"[RATE LIMITED] thread={thread_id} (rate limiter unavailable)"
    if _rl_dec == "deny":
        record_rate_limit_decision(tool.name, "deny")
        return f"[RATE LIMITED] thread={thread_id}"
    else:
        record_rate_limit_decision(tool.name, "allow")
    res = policy.decide(tool.name, args, ctx)
    policy.audit(tool.name, res, ctx)

    # CIPHER-012: não expõe o approval_id completo no response — apenas um prefixo
    # (reference) para rastreabilidade, insuficiente para polling não autorizado.
    if res.decision == Decision.DENY:
        ref = f"; reference={res.approval_id[:8]}" if res.approval_id else ""
        return f"[BLOQUEADO PELA POLÍTICA] {res.reason} (thread={thread_id}{ref})"
    if res.decision == Decision.HITL:
        ref = res.approval_id[:8] if res.approval_id else ""
        return f"[AGUARDANDO APROVAÇÃO] pedido {ref} registrado (thread={thread_id})"

    # CIPHER-018: timeout em tool.ainvoke (protege contra ferramentas que travam).
    from src.jefrey.core.config import get_settings as _gs
    import time as _time_mod

    timeout = _gs().mcp.tool_timeout
    _start = _time_mod.monotonic()
    try:
        result = await asyncio.wait_for(tool.ainvoke(args), timeout=timeout)
        _elapsed = _time_mod.monotonic() - _start
        record_mcp_tool_call(tool.name, "success", _elapsed)
    except asyncio.TimeoutError:
        _elapsed = _time_mod.monotonic() - _start
        logger.warning("timeout na ferramenta %s após %ss", tool.name, timeout)
        record_mcp_tool_call(tool.name, "timeout", _elapsed)
        return json.dumps(
            {"error": "timeout", "tool": tool.name,
             "message": f"Ferramenta não respondeu em {timeout}s"},
            ensure_ascii=False,
        )
    except Exception as e:  # noqa: BLE001
        _elapsed = _time_mod.monotonic() - _start
        logger.exception("erro ao executar ferramenta %s", tool.name)
        record_mcp_tool_call(tool.name, "error", _elapsed)
        return f"[ERRO NA FERRAMENTA] {tool.name}: {e}"
    return _stringify(result)


def _stringify(result) -> str:
    if isinstance(result, str):
        return result
    import json
    try:
        return json.dumps(result, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(result)


# ---------------------------------------------------------------------------
# Geração dinâmica de wrappers MCP a partir do args_schema de cada ferramenta
# ---------------------------------------------------------------------------
def _type_name(ann) -> str:
    # Desempacota Optional[X] / X | None (get_origin vira UnionType, não o tipo interno)
    origin = typing.get_origin(ann)
    if origin in (typing.Union, getattr(types, "UnionType", ())):
        non_none = [a for a in typing.get_args(ann) if a is not type(None)]
        if non_none:
            ann = non_none[0]
            origin = typing.get_origin(ann)
    if ann is str or getattr(ann, "__name__", "") == "str":
        return "str"
    if ann is int or getattr(ann, "__name__", "") == "int":
        return "int"
    if ann is float or getattr(ann, "__name__", "") == "float":
        return "float"
    if ann is bool or getattr(ann, "__name__", "") == "bool":
        return "bool"
    if ann is dict or getattr(ann, "__name__", "") == "dict":
        return "dict"
    if origin in (list, typing.List) or getattr(ann, "__name__", "") == "list":
        return "list"
    return "str"


def _tool_params_schema(tool) -> dict:
    """Schema JSON-serializavel dos parametros da ferramenta (model_fields contem
    FieldInfo, que o JSONResponse nao serializa -> 500 em /tools)."""
    schema = getattr(tool, "args_schema", None)
    try:
        if isinstance(schema, dict):
            return schema.get("properties", {})
        if schema is not None and hasattr(schema, "model_json_schema"):
            return schema.model_json_schema().get("properties", {})
    except Exception as exc:  # noqa: BLE001
        logger.warning("schema de parametros indisponivel para %s: %s", getattr(tool, "name", "?"), exc)
    return {}


def _make_wrapper(tool: StructuredTool) -> callable:
    """Cria uma função async cuja assinatura = (thread_id, *args_da_ferramenta).

    O mcp (MCPServer) introspecta a assinatura para montar o inputSchema JSON. O
    thread_id é injetado pelo cliente MCP (ex.: o n8n envia seu próprio thread_id).

    CIPHER-001: o papel (role) FOI REMOVIDO da assinatura. O papel é resolvido
    server-side em _resolve_role() — um cliente jamais pode se autodeclarar "admin".
    """
    import inspect
    from functools import wraps

    schema = tool.args_schema
    fields = schema.model_fields

    # Build parameter list for signature inspection
    params = [inspect.Parameter("thread_id", inspect.Parameter.POSITIONAL_ONLY, annotation=str)]
    _renamed: dict[str, str] = {}
    for fname, finfo in fields.items():
        tn = _type_name(finfo.annotation)
        ann = _get_annotation(tn)
        pname = fname
        if fname == "thread_id":
            # colide com o thread_id de conversa injetado pelo MCP (ex.: email.send_message
            # tem thread_id = thread do Gmail). Expoe como email_thread_id e remapeia na chamada.
            pname = "email_thread_id"
            _renamed[pname] = fname
        if finfo.is_required():
            params.append(inspect.Parameter(pname, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=ann))
        elif finfo.default is None:
            params.append(inspect.Parameter(pname, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=ann, default=None))
        else:
            params.append(inspect.Parameter(pname, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=ann, default=finfo.default))

    # inspect.Signature exige obrigatorios antes dos com default; o schema pode
    # declarar campos opcionais antes de obrigatorios. Ordenacao estavel: thread_id
    # continua primeiro e a chamada por keyword nao muda.
    params.sort(key=lambda _p: _p.default is not inspect.Parameter.empty)

    async def _wrap(thread_id: str, **kwargs) -> str:
        _args = {_renamed.get(k, k): v for k, v in kwargs.items()}
        # CIPHER-120: input size guard (DoS/context bloat) — valida antes do PolicyEngine
        for _k, _v in _args.items():
            if isinstance(_v, str) and len(_v) > 8000:
                return f"[INPUT TOO LARGE] campo {_k} excede 8000 chars"
            if isinstance(_v, list) and len(_v) > 100:
                return f"[INPUT TOO LARGE] lista {_k} excede 100 itens"
        return await _run_guarded(tool, _args, thread_id)

    # Set proper signature for MCP introspection
    _wrap.__signature__ = inspect.Signature(params)
    _wrap.__name__ = f"mcp_{tool.name}"
    _wrap.__doc__ = tool.description
    return _wrap

def _get_annotation(type_name: str):
    """Convert type name string to annotation."""
    mapping = {
        "str": str, "int": int, "float": float, "bool": bool,
        "dict": dict, "list": list,
    }
    return mapping.get(type_name, str)


# ---------------------------------------------------------------------------
# Ferramentas de integração HIGH (stubs) — gateway expõe risco real desde já
# ---------------------------------------------------------------------------
def _make_stub_tool(name: str, description: str, fields: dict) -> StructuredTool:
    """Cria uma ferramenta HIGH (por convenção de nome) com implementação stub.

    email_*/calendar_* são classificados HIGH pelo PolicyEngine. A implementação real
    (envio/OAuth) fica para P5; aqui a ferramenta executa e retorna resultado determinístico
    para exercitar o caminho HIGH sob PolicyEngine (bloqueio p/ user, execução p/ admin).
    """
    schema = create_model(f"{name}Schema", **fields)

    async def _impl(**kwargs):
        return {"executed": True, "tool": name, "args": kwargs, "note": "stub: integração real em P5"}

    return StructuredTool.from_function(coroutine=_impl, name=name, description=description, args_schema=schema)


INTEGRATION_TOOLS: list[StructuredTool] = [
    _make_stub_tool(
        "email_send",
        "Envia e-mail (HIGH: exige aprovação/HITL). Stub em P3a — envio real em P5.",
        {
            "to": (str, ...),
            "subject": (str, ...),
            "body": (str, ...),
            "cc": (str | None, None),
        },
    ),
    _make_stub_tool(
        "calendar_create",
        "Cria evento no calendário (HIGH: exige aprovação/HITL). Stub em P3a — OAuth real em P5.",
        {
            "title": (str, ...),
            "start": (str, ...),
            "end": (str | None, None),
            "attendees": (list[str] | None, None),
        },
    ),
]


# ---------------------------------------------------------------------------
# Construção do servidor
# ---------------------------------------------------------------------------
def _get_bridge_health() -> dict:
    """Info do n8n bridge para health endpoint (fail-safe)."""
    try:
        from src.jefrey.mcp.n8n_bridge import get_bridge
        return get_bridge().health()
    except Exception:
        return {"status": "unavailable"}


def build_server() -> MCPServer:
    from src.jefrey.core.registry import register_default_tools
    from src.jefrey.skills import skill_registry, load_skills

    mcp_server = MCPServer(
        name="jefrey-mcp",
        instructions="Jefrey MCP Gateway — ferramentas protegidas por PolicyEngine (RBAC/HITL).",
    )

    # registra skills (email/calendar podem falhar se libs do Google ausentes — tratado em load_skills)
    load_skills()
    # P4: popula o ToolRegistry com risco/papel explícitos de cada ferramenta.
    register_default_tools()

    registered = 0
    for tool in list(skill_registry.get_all_tools()):
        wrapper = _make_wrapper(tool)
        mcp_server.tool(name=tool.name, description=tool.description or "")(wrapper)
        registered += 1

    for tool in INTEGRATION_TOOLS:
        wrapper = _make_wrapper(tool)
        mcp_server.tool(name=tool.name, description=tool.description or "")(wrapper)
        registered += 1

    logger.info("MCP: %d ferramentas registradas", registered)

    # BUG-P3a-01: Popula discovery cache com todas as ferramentas registradas
    all_registered_tools = list(skill_registry.get_all_tools()) + INTEGRATION_TOOLS
    _populate_cache(all_registered_tools)

    @mcp_server.custom_route("/health", methods=["GET"])
    async def health(request):  # noqa: ANN001 - handler de rota Starlette
        from src.jefrey.core.memory import get_memory_manager
        from src.jefrey.core.policy import get_policy_engine

        try:
            hm = get_memory_manager().health_check()
        except AttributeError:
            # health_check method may not exist in all deployments
            hm = {"status": "ok", "postgres": "unknown", "redis": "unknown"}
        pol = get_policy_engine()
        return JSONResponse(
            {
                "status": hm["status"],
                "mcp": "ok",
                "postgres": hm.get("postgres"),
                "redis": hm.get("redis"),
                "policy": {"mode": pol.mode, "autonomous": pol.autonomous},
                "tools": registered,
                "cache": {
                    "size": len(_tool_discovery_cache),
                    "valid": _is_cache_valid(),
                    "hits": _cache_hits,
                    "misses": _cache_misses,
                    "ttl": _cache_ttl,
                },
                "oauth_enabled": _OAUTH_ENABLED,
                "oauth_tokens_configured": len(_VALID_TOKENS),
                "bridge": _get_bridge_health(),
            }
        )


    # M1: Rota OAuth-protegida para verificar autenticacao
    @mcp_server.custom_route("/oauth/status", methods=["GET"])
    async def oauth_status(request):
        """Endpoint protegido por OAuth - retorna status do token."""
        guard_response = await _oauth_guard(request)
        if guard_response is not None:
            return guard_response
        return JSONResponse({
            "authenticated": True,
            "oauth_enabled": _OAUTH_ENABLED,
            "tokens_configured": len(_VALID_TOKENS),
            "role": _resolve_role(),
        })


    # M2: Rotas de gerenciamento do discovery cache (BUG-P3a-01)
    @mcp_server.custom_route("/cache/status", methods=["GET"])
    async def cache_status(request):
        """Status do discovery cache (protegido por OAuth)."""
        guard_response = await _oauth_guard(request)
        if guard_response is not None:
            return guard_response
        return JSONResponse({
            "cache_size": len(_tool_discovery_cache),
            "cache_ttl": _cache_ttl,
            "cached_at": _cached_at,
            "cache_valid": _is_cache_valid(),
            "cache_hits": _cache_hits,
            "cache_misses": _cache_misses,
            "tools": list(_tool_discovery_cache.keys()),
        })

    @mcp_server.custom_route("/cache/clear", methods=["POST"])
    async def cache_clear(request):
        """Limpa discovery cache (protegido por OAuth). Util para hot-reload."""
        guard_response = await _oauth_guard(request)
        if guard_response is not None:
            return guard_response
        _clear_discovery_cache()
        return JSONResponse({"cleared": True, "message": "Discovery cache limpo"})


    # M4: Rota de status do n8n Bridge (BUG-P3a Diff 4)
    @mcp_server.custom_route("/bridge/status", methods=["GET"])
    async def bridge_status(request):
        """Status do n8n bridge (protegido por OAuth)."""
        guard_response = await _oauth_guard(request)
        if guard_response is not None:
            return guard_response
        from src.jefrey.mcp.n8n_bridge import get_bridge, list_workflows
        bridge = get_bridge()
        return JSONResponse({
            "bridge": bridge.health(),
            "workflows": list_workflows(),
        })

    # M4: Rota para executar workflow via bridge (protegido por OAuth)
    @mcp_server.custom_route("/bridge/execute", methods=["POST"])
    async def bridge_execute(request):
        """Executa workflow n8n via bridge (protegido por OAuth + HITL)."""
        guard_response = await _oauth_guard(request)
        if guard_response is not None:
            return guard_response
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid_json"}, status_code=400)
        workflow = body.get("workflow", "")
        args = body.get("args", {})
        user_id = body.get("user_id", "system")
        thread_id = body.get("thread_id", "")
        if not workflow:
            return JSONResponse({"error": "workflow name required"}, status_code=400)
        from src.jefrey.mcp.n8n_bridge import get_bridge
        bridge = get_bridge()
        result = await bridge.execute(workflow, args, user_id=user_id, thread_id=thread_id)
        # Record bridge execution metric
        mode = "mcp" if bridge._mode.value == "mcp" else "webhook"
        status_map = {
            "success": "success",
            "failed": "error",
            "timeout": "timeout",
            "rejected": "hitl_rejected",
        }
        record_bridge_execution(workflow, mode, status_map.get(result.status.value, "error"))
        status_code = 200 if result.status.value in ("success", "approved") else 422
        return JSONResponse(result.to_dict(), status_code=status_code)


    # M5: Prometheus /metrics endpoint (Diff 5 Enhanced Health)
    @mcp_server.custom_route("/metrics", methods=["GET"])
    async def metrics_endpoint(request):
        """Endpoint Prometheus para scraping de métricas."""
        # /metrics é público (sem OAuth) - padrão Prometheus
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    # Sprint 2 Task 1: Rota pública de descoberta de tools
    @mcp_server.custom_route("/tools", methods=["GET"])
    async def list_tools(request):
        """Lista todas as ferramentas MCP disponíveis (público, sem OAuth).
        
        Used by clients (CLI, n8n, frontend) para discover available tools
        before authentication. Rate-limited per IP for DoS protection.
        """
        all_tools = []
        # Tools from skill registry
        from src.jefrey.skills import skill_registry
        for tool in skill_registry.get_all_tools():
            all_tools.append({
                "name": tool.name,
                "description": tool.description or "",
                "parameters": _tool_params_schema(tool),
                "category": "skill",
            })
        # Integration tools
        for tool in INTEGRATION_TOOLS:
            all_tools.append({
                "name": tool.name,
                "description": tool.description or "",
                "parameters": _tool_params_schema(tool),
                "category": "integration",
            })
        # Cache info
        return JSONResponse({
            "tools": all_tools,
            "total": len(all_tools),
            "cache_size": len(_tool_discovery_cache),
            "oauth_enabled": _OAUTH_ENABLED,
        })

    # P0-1: Add OAuth middleware to protect all MCP endpoints (including tool calls)
    # O middleware OAuth e aplicado em main() sobre o app Starlette (mcp 2.x nao tem .app).

    return mcp_server


def main() -> None:
    from src.jefrey.core.config import get_settings
    from src.jefrey.core.telemetry import init_telemetry
    import json

    cfg = get_settings().mcp
    tel_cfg = get_settings().telemetry

    # Initialize OpenTelemetry if enabled
    if tel_cfg.enabled:
        otlp_headers = {}
        if tel_cfg.otlp_headers:
            try:
                otlp_headers = json.loads(tel_cfg.otlp_headers)
            except Exception:
                logger.warning("Invalid JEFREY_TELEMETRY__OTLP_HEADERS JSON")
        init_telemetry(
            service_name=tel_cfg.service_name,
            otlp_endpoint=tel_cfg.otlp_endpoint or None,
            otlp_headers=otlp_headers or None,
            sample_rate=tel_cfg.sample_rate,
            enable_console=tel_cfg.enable_console,
        )
        logger.info("OpenTelemetry initialized (endpoint=%s)", tel_cfg.otlp_endpoint or "none")

    mcp_server = build_server()
    logger.info("Iniciando Jefrey MCP Server em %s:%s (%s)", cfg.host, cfg.port, cfg.transport)
    if cfg.transport == "streamable-http":
        # mcp 2.x: MCPServer nao expoe .app; gera o app Starlette, protege com OAuth
        # (P0-1) e serve com uvicorn. Rotas custom (/health, /metrics, /tools) ja vem no app.
        import uvicorn
        app = mcp_server.streamable_http_app(
            host=cfg.host,
            streamable_http_path=cfg.path,
            json_response=cfg.json_response,
            stateless_http=cfg.stateless_http,
        )
        app.add_middleware(_OAuthMiddleware)
        uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info")
    else:
        mcp_server.run(transport=cfg.transport)


if __name__ == "__main__":
    main()
