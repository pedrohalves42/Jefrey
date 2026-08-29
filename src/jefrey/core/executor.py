"""Tool Executor — orquestra RBAC -> PolicyEngine -> HITL(polling) -> execução (P4).

Usado pelo agent loop (JefreyAgent._execute_tools) e por scripts de verificação.
Centraliza a lógica de segurança para que o LLM não precise conhecê-la.

AXIOM #1: RBAC é checado ANTES do PolicyEngine.
AXIOM #2/#3: HIGH/CRITICAL em modo human-in-the-loop cria approval e aguarda
            decisão REST; aprovar -> executa; rejeitar/expirar -> bloqueia + audit.
AXIOM #4: admin bypassa HITL e executa direto (audit role=admin).
AXIOM #5: risco vem do ToolRegistry (declarado); não registrado -> UNKNOWN -> bloqueado.

Nota de estrutura: este módulo é leve (não importa LangGraph) para ser testável
de forma determinística por verify_p4 — é a implementação do "polling de approval"
listado no escopo de P4 (fatorado de agent.py para isolamento de dependências).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Awaitable

from src.jefrey.core.rbac import Role, as_role, RBACEngine
from src.jefrey.core.registry import TOOL_REGISTRY
from src.jefrey.core.policy import get_policy_engine, PolicyContext, Decision
from src.jefrey.core.hitl import ApprovalManager
from src.jefrey.core.audit import audit_tool_call

logger = logging.getLogger(__name__)

ToolResolver = Callable[[str], Any]  # name -> BaseTool | callable | None


@dataclass
class ToolExecutionResult:
    executed: bool = False
    blocked: bool = False
    decision: str = ""
    reason: str = ""
    approval_id: str | None = None
    result: Any = None


class ToolExecutor:
    def __init__(
        self,
        tool_resolver: ToolResolver,
        *,
        actor_role: str = "user",
        autonomous: bool = False,
        thread_id: str = "default",
    ) -> None:
        self._resolve = tool_resolver
        self._actor_role = as_role(actor_role)
        self._autonomous = autonomous
        self._thread_id = thread_id
        self._rbac = RBACEngine()
        self._hitl = ApprovalManager()
        self._policy = get_policy_engine()

    async def execute(
        self, tool_name: str, args: dict | None = None, thread_id: str | None = None,
    ) -> ToolExecutionResult:
        tid = thread_id or self._thread_id
        actor = self._actor_role
        args = args or {}

        # --- AXIOM #1: RBAC antes do PolicyEngine ---
        required = TOOL_REGISTRY.required_role_of(tool_name) or Role.USER
        rbac_res = self._rbac.check(actor, required, tool_name)
        if rbac_res.decision == "deny":
            rk = TOOL_REGISTRY.risk_of(tool_name)
            risk_str = rk.value if rk is not None else "unknown"
            audit_tool_call(
                thread_id=tid, tool_name=tool_name, actor_role=actor.value,
                risk=risk_str, decision="deny_rbac", reason=rbac_res.reason, source="agent",
            )
            return ToolExecutionResult(
                blocked=True, decision="deny_rbac", reason=rbac_res.reason,
            )

        # --- PolicyEngine ---
        ctx = PolicyContext(thread_id=tid, user_role=actor.value, autonomous=self._autonomous)
        res = self._policy.decide(tool_name, args, ctx)
        risk_val = res.risk.value

        if res.decision == Decision.DENY:
            audit_tool_call(
                thread_id=tid, tool_name=tool_name, actor_role=actor.value,
                risk=risk_val, decision="deny", reason=res.reason,
                approval_id=res.approval_id, source="agent",
            )
            return ToolExecutionResult(
                blocked=True, decision="deny", reason=res.reason, approval_id=res.approval_id,
            )

        if res.decision == Decision.ALLOW:
            audit_tool_call(
                thread_id=tid, tool_name=tool_name, actor_role=actor.value,
                risk=risk_val, decision="allow", reason=res.reason, source="agent",
            )
            return ToolExecutionResult(
                executed=True, decision="allow",
                result=await self._invoke(tool_name, args),
            )

        # --- HITL: aguarda decisão humana (AXIOM #2/#3/#4) ---
        approval_id = res.approval_id
        audit_tool_call(
            thread_id=tid, tool_name=tool_name, actor_role=actor.value,
            risk=risk_val, decision="hitl", reason=res.reason,
            approval_id=approval_id, source="agent",
        )
        final = await self._hitl.wait_for_decision(approval_id, timeout=self._hitl._ttl)
        if final == "approved":
            audit_tool_call(
                thread_id=tid, tool_name=tool_name, actor_role=actor.value,
                risk=risk_val, decision="allow", approval_id=approval_id,
                approval_decision="approved", source="agent",
            )
            return ToolExecutionResult(
                executed=True, decision="allow",
                result=await self._invoke(tool_name, args), approval_id=approval_id,
            )
        # rejected | expired | not_found
        audit_tool_call(
            thread_id=tid, tool_name=tool_name, actor_role=actor.value,
            risk=risk_val, decision="deny", approval_id=approval_id,
            approval_decision=final, reason=f"approval {final}", source="agent",
        )
        return ToolExecutionResult(
            blocked=True, decision="deny", reason=f"approval {final}", approval_id=approval_id,
        )

    async def _invoke(self, tool_name: str, args: dict) -> Any:
        tool = self._resolve(tool_name)
        if tool is None:
            return f"[ERRO] ferramenta '{tool_name}' não resolvida"
        if hasattr(tool, "ainvoke"):
            return await tool.ainvoke(args)
        return await tool(**args)
