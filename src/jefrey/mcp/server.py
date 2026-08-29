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

import sys
import os
import types
import typing
import logging
import asyncio
import contextvars
import json
from pathlib import Path

# garante que o pacote 'src' seja importável independente de como o processo sobe
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mcp.server.mcpserver import MCPServer
from starlette.responses import JSONResponse

from pydantic import create_model
from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)

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

    timeout = _gs().mcp.tool_timeout
    try:
        result = await asyncio.wait_for(tool.ainvoke(args), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("timeout na ferramenta %s após %ss", tool.name, timeout)
        return json.dumps(
            {"error": "timeout", "tool": tool.name,
             "message": f"Ferramenta não respondeu em {timeout}s"},
            ensure_ascii=False,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("erro ao executar ferramenta %s", tool.name)
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


def _make_wrapper(tool: StructuredTool) -> callable:
    """Cria uma função async cuja assinatura = (thread_id, *args_da_ferramenta).

    O mcp (MCPServer) introspecta a assinatura para montar o inputSchema JSON. O
    thread_id é injetado pelo cliente MCP (ex.: o n8n envia seu próprio thread_id).

    CIPHER-001: o papel (role) FOI REMOVIDO da assinatura. O papel é resolvido
    server-side em _resolve_role() — um cliente jamais pode se autodeclarar "admin".
    """
    schema = tool.args_schema
    fields = schema.model_fields
    ns: dict = {"str": str, "int": int, "float": float, "bool": bool, "dict": dict, "list": list}
    ns["_run_guarded"] = _run_guarded
    ns["_TOOL"] = tool

    # ordem: obrigatórios primeiro (thread_id + campos obrigatórios da ferramenta),
    # depois opcionais (campos opcionais da ferramenta).
    required_params = ["thread_id: str"]
    optional_params: list[str] = []
    for fname, finfo in fields.items():
        tn = _type_name(finfo.annotation)
        if finfo.is_required():
            required_params.append(f"{fname}: {tn}")
        elif finfo.default is None:
            optional_params.append(f"{fname}: {tn} = None")
        else:
            optional_params.append(f"{fname}: {tn} = {repr(finfo.default)}")
    params = required_params + optional_params

    src = (
        f"async def _wrap({', '.join(params)}) -> str:\n"
        f"    _args = {{k: v for k, v in locals().items() if k not in ('thread_id',)}}\n"
        f"    return await _run_guarded(_TOOL, _args, thread_id)\n"
    )
    exec(src, ns)
    wrapper = ns["_wrap"]
    wrapper.__name__ = f"mcp_{tool.name}"
    wrapper.__doc__ = tool.description
    return wrapper


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
def build_server() -> MCPServer:
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

    @mcp_server.custom_route("/health", methods=["GET"])
    async def health(request):  # noqa: ANN001 - handler de rota Starlette
        from src.jefrey.core.memory import get_memory_manager
        from src.jefrey.core.policy import get_policy_engine

        hm = get_memory_manager().health_check()
        pol = get_policy_engine()
        return JSONResponse(
            {
                "status": hm["status"],
                "mcp": "ok",
                "postgres": hm.get("postgres"),
                "redis": hm.get("redis"),
                "policy": {"mode": pol.mode, "autonomous": pol.autonomous},
                "tools": registered,
            }
        )

    return mcp_server


def main() -> None:
    from src.jefrey.core.config import get_settings

    cfg = get_settings().mcp
    mcp_server = build_server()
    logger.info("Iniciando Jefrey MCP Server em %s:%s (%s)", cfg.host, cfg.port, cfg.transport)
    mcp_server.run(
        transport=cfg.transport,
        host=cfg.host,
        port=cfg.port,
        streamable_http_path=cfg.path,
        json_response=cfg.json_response,
        stateless_http=cfg.stateless_http,
    )


if __name__ == "__main__":
    main()
