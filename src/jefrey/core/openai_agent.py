"""Agente Jefrey usando OpenAI Agents SDK & Responses API (Fase P2).

Este módulo é o novo runtime "openai" (selecionável via JEFREY_AGENT__PROVIDER=openai).
Substitui o LangGraph/MemorySaver por:
  - `OpenAIAgent` (SDK Agents: Agent + Runner + Responses API)
  - `PostgresSessionStore` (persistência de sessão por thread_id em PostgreSQL)

As ferramentas LangChain existentes (skills) são convertidas para `function_tool`
preservando o schema Pydantic. Uma ferramenta `memory_search` dá ao agente acesso
à memória de longo prazo (Postgres+pgvector) já construída na Fase 1.

Observação: o provider "openai" requer um endpoint compatível com a *Responses API*
da OpenAI (ex.: api.openai.com). Ollama não implementa a Responses API, por isso o
default do sistema continua sendo "langgraph" (que funciona com Ollama).
"""
from __future__ import annotations

import inspect
import logging
import os
from typing import Any

from pydantic_core import PydanticUndefined
from langchain_core.tools import BaseTool

from agents import (
    Agent,
    Runner,
    function_tool,
    set_default_openai_key,
    set_tracing_disabled,
    RunContextWrapper,
)

from src.jefrey.core.config import get_settings
from src.jefrey.core.memory import get_memory_manager
from src.jefrey.core.events import event_bus, SystemEvents
from src.jefrey.core.policy import (
    PolicyEngine,
    PolicyContext,
    RunContext,
    Decision,
    get_policy_engine,
)

# Ativa logging estruturado (JSON) no runtime do agente.
import src.jefrey.core.logging  # noqa: F401

logger = logging.getLogger(__name__)

# Modelo de sessão registrado sob demanda (primeira vez que PostgresSessionStore é instanciado).
_AGENT_SESSION_MODEL = None


def _ensure_agent_config() -> None:
    """Aplica key/base URL do OpenAI e desliga tracing (evita chamadas ao collector)."""
    cfg = get_settings().agent
    if cfg.openai_api_key:
        set_default_openai_key(cfg.openai_api_key)
    if cfg.openai_base_url:
        # agents 0.22 não expõe set_default_openai_base_url; usamos a env var do cliente.
        os.environ.setdefault("OPENAI_BASE_URL", cfg.openai_base_url)
    set_tracing_disabled(True)


def _convert_tool(lc_tool: BaseTool, policy: PolicyEngine | None = None):
    """Converte um LangChain BaseTool em um `function_tool` do OpenAI Agents SDK.

    Reconstrói a assinatura a partir de `args_schema.model_fields` para que o schema
    JSON da ferramenta seja fiel ao original. O primeiro parâmetro `ctx` recebe o
    RunContextWrapper (usado para aplicar o PolicyEngine antes de executar a ferramenta).
    """
    schema = lc_tool.args_schema
    fields = schema.model_fields if schema is not None else {}

    async def _invoke(ctx: RunContextWrapper, **kwargs):
        async def _run():
            return await lc_tool.ainvoke(kwargs)
        return await _guarded_call(lc_tool.name, _run, policy, ctx, kwargs)

    if not fields:
        return function_tool(
            _invoke,
            name_override=lc_tool.name,
            description_override=lc_tool.description or "",
            strict_mode=False,
        )

    params = [inspect.Parameter("ctx", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=RunContextWrapper)]
    annotations: dict[str, Any] = {"ctx": RunContextWrapper}
    for name, fld in fields.items():
        annotations[name] = fld.annotation
        default = inspect.Parameter.empty if fld.is_required() else fld.default
        params.append(
            inspect.Parameter(
                name,
                inspect.Parameter.KEYWORD_ONLY,
                default=default,
                annotation=fld.annotation,
            )
        )
    _invoke.__signature__ = inspect.Signature(params)
    _invoke.__annotations__ = annotations
    return function_tool(
        _invoke,
        name_override=lc_tool.name,
        description_override=lc_tool.description or "",
        strict_mode=False,
    )


async def _guarded_call(tool_name: str, original_coro_factory, policy, ctx, args):
    """Aplica o PolicyEngine e executa (ou bloqueia) a ferramenta, auditando o call."""
    rc = ctx.context if ctx is not None else None
    thread_id = getattr(rc, "thread_id", "default") if rc else "default"
    pctx = PolicyContext(
        thread_id=thread_id,
        user_role=getattr(rc, "user_role", "user"),
        user_id=getattr(rc, "user_id", "system"),  # SECURITY: multi-tenant isolation
        autonomous=getattr(rc, "autonomous", True),
    )
    if policy is None:
        return await original_coro_factory()
    res = policy.decide(tool_name, args, pctx)
    policy.audit(tool_name, res, pctx)
    if res.decision == Decision.ALLOW:
        return await original_coro_factory()
    if res.decision == Decision.HITL:
        return f"[AGUARDANDO APROVAÇÃO] pedido {res.approval_id} registrado: {res.reason}"
    return f"[BLOQUEADO PELA POLÍTICA] {res.reason}"


class PostgresSessionStore:
    """Persistência de sessões do agente (thread_id -> itens da conversa) em PostgreSQL.

    Armazena a lista de itens da Responses API (`result.to_input_list()`) em JSONB,
    permitindo retomar a conversa exatamente de onde parou em qualquer reinício.
    """

    def __init__(self):
        from src.jefrey.core.db import get_db, get_engine
        from src.jefrey.core.models import Base
        from sqlalchemy import Column, String, DateTime, func
        from sqlalchemy.dialects.postgresql import JSONB

        # Declara o modelo uma única vez (registrado em Base.metadata).
        global _AGENT_SESSION_MODEL
        if _AGENT_SESSION_MODEL is None:

            class AgentSession(Base):  # type: ignore[misc, valid-type]
                __tablename__ = "agent_sessions"

                thread_id = Column(String(256), primary_key=True)
                items = Column(JSONB, nullable=False, default=lambda: [])
                updated_at = Column(
                    DateTime(timezone=True),
                    server_default=func.now(),
                    onupdate=func.now(),
                )

            _AGENT_SESSION_MODEL = AgentSession

        self._model = _AGENT_SESSION_MODEL
        # Garante a tabela (idempotente).
        Base.metadata.create_all(get_engine(), tables=[self._model.__table__])

    async def load(self, thread_id: str) -> list:
        from src.jefrey.core.db import get_db

        with get_db() as s:
            row = s.get(self._model, thread_id)
            return list(row.items) if row else []

    async def save(self, thread_id: str, items: list) -> None:
        from src.jefrey.core.db import get_db

        with get_db() as s:
            row = s.get(self._model, thread_id)
            if row is None:
                s.add(self._model(thread_id=thread_id, items=items))
            else:
                row.items = items
            s.commit()

    async def clear(self, thread_id: str) -> None:
        from src.jefrey.core.db import get_db

        with get_db() as s:
            row = s.get(self._model, thread_id)
            if row is not None:
                s.delete(row)
                s.commit()


class OpenAIAgent:
    """Runtime do Jefrey baseado em OpenAI Agents SDK & Responses API."""

    def __init__(self, tools: list[BaseTool] | None = None, model: str | None = None):
        if tools is None:
            from src.jefrey.skills import skill_registry, load_skills

            load_skills()
            tools = skill_registry.get_all_tools()

        self.tools_lc = list(tools)
        self.memory = get_memory_manager()
        cfg = get_settings().agent
        self.model = model or cfg.openai_model
        self._policy = get_policy_engine()

        self._agent_tools = [_convert_tool(t, self._policy) for t in self.tools_lc]
        self._agent_tools.append(self._make_memory_tool())

        self._agent = Agent(
            name="Jefrey",
            instructions=cfg.system_prompt,
            tools=self._agent_tools,
            model=self.model,
        )
        self._sessions = PostgresSessionStore()
        _ensure_agent_config()

    def _make_memory_tool(self):
        memory = self.memory
        policy = self._policy

        @function_tool(
            name_override="memory_search",
            description_override=(
                "Busca memórias de longo prazo relevantes do Jefrey "
                "(episódios, semânticas, preferências). Use para contextualizar respostas."
            ),
            strict_mode=False,
        )
        async def memory_search(ctx: RunContextWrapper, query: str, top_k: int = 5) -> str:
            async def _run():
                try:
                    res = memory.long_term.search(query, top_k=top_k)
                except Exception as e:  # noqa: BLE001
                    return f"Erro ao buscar memória: {e}"
                if not res:
                    return "Sem memórias relevantes."
                return "\n".join(
                    f"[{m.get('similarity', 0):.0%}] {m['content']}" for m in res
                )
            return await _guarded_call("memory_search", _run, policy, ctx, {"query": query, "top_k": top_k})

        return memory_search

    async def run(self, user_input: str, thread_id: str = "default") -> str:
        logger.info("run inicio thread=%s input_len=%d", thread_id, len(user_input))
        history = await self._sessions.load(thread_id)
        run_input = history + [{"role": "user", "content": user_input}]

        result = await Runner.run(
            self._agent, input=run_input,
            context=RunContext(thread_id=thread_id, autonomous=self._policy.autonomous),
        )
        await self._sessions.save(thread_id, result.to_input_list())
        final = result.final_output

        await event_bus.emit_sync(
            SystemEvents.USER_MESSAGE, {"input": user_input, "thread_id": thread_id}
        )
        try:
            self.memory.add_conversation(user_input, final)
        except Exception as e:  # noqa: BLE001
            logger.error("Falha ao salvar conversa na memória: %s", e)
        await event_bus.emit_sync(
            SystemEvents.ASSISTANT_RESPONSE,
            {"response": final, "thread_id": thread_id},
        )
        logger.info("run fim thread=%s", thread_id)
        return final

    async def stream(self, user_input: str, thread_id: str = "default", user_id: str = "system"):
        history = await self._sessions.load(thread_id)
        run_input = history + [{"role": "user", "content": user_input}]

        result = Runner.run_streamed(
            self._agent, input=run_input,
            context=RunContext(thread_id=thread_id, user_id=user_id, autonomous=self._policy.autonomous),
        )
        async for event in result.stream_events():
            data = getattr(event, "data", None)
            delta = getattr(data, "delta", None) if data is not None else None
            if delta:
                yield delta

        await self._sessions.save(thread_id, result.to_input_list())
        final = result.final_output
        try:
            self.memory.add_conversation(user_input, final)
        except Exception as e:  # noqa: BLE001
            logger.error("Falha ao salvar conversa na memória: %s", e)

    async def health_check(self) -> dict:
        try:
            await self._sessions.load("__health__")
            store_ok = True
        except Exception as e:  # noqa: BLE001
            store_ok = False
            logger.error("Health check session store falhou: %s", e)
        return {
            "status": "healthy" if store_ok else "degraded",
            "llm": "openai(configurado)",
            "memory": "ok" if store_ok else "error",
            "policy": "disabled" if self._policy.mode == "off" else "enabled",
            "policy_mode": self._policy.mode,
            "tools_available": len(self.tools_lc),
            "version": get_settings().version,
        }
