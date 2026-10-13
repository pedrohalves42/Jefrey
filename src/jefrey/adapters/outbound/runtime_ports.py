"""Liga as portas da execucao de ferramentas aos modulos que fazem o trabalho (auditoria, metricas, aprovacao humana, filtro de texto).
Os imports sao feitos na hora do uso: os modulos podem ser trocados em teste e uma falha de um deles nao derruba a partida."""
from __future__ import annotations


class SqlToolAudit:
    def tool_call(self, *, thread_id, tool_name, actor_role, risk, decision, reason, approval_id, approval_decision, user_id) -> None:
        from src.jefrey.core.audit import audit_tool_call

        audit_tool_call(thread_id=thread_id, tool_name=tool_name, actor_role=actor_role, risk=risk, decision=decision, reason=reason,
                        approval_id=approval_id, approval_decision=approval_decision, source="agent", user_id=user_id)


class PrometheusToolMetrics:
    def tool_blocked(self, tool: str, reason: str) -> None:
        from src.jefrey.core.metrics import TOOLS_BLOCKED

        TOOLS_BLOCKED.labels(tool_name=tool, reason=reason).inc()

    def tool_latency(self, tool: str, seconds: float) -> None:
        from src.jefrey.core.metrics import TOOL_EXEC_LATENCY

        TOOL_EXEC_LATENCY.labels(tool_name=tool).observe(seconds)


class HumanApprovalGate:
    def __init__(self) -> None:
        self._mgrs: dict = {}

    def create(self, **kw) -> str:
        from src.jefrey.core.hitl import ApprovalManager

        mgr = ApprovalManager()
        approval_id = mgr.create(**kw)
        self._mgrs[approval_id] = mgr
        return approval_id

    async def wait_for_decision(self, approval_id: str, timeout=None) -> str:
        from src.jefrey.core.hitl import ApprovalManager

        mgr = self._mgrs.pop(approval_id, None) or ApprovalManager()
        return await mgr.wait_for_decision(approval_id, timeout=timeout)


class ContentGuard:
    def sanitize(self, text: str, source: str = "") -> str:
        from src.jefrey.core.content_guard import sanitize_tool_output

        return sanitize_tool_output(text, source=source)


class TodayPrefs:
    def home_city(self) -> str:
        from src.jefrey.core import today

        return today.load_prefs().get("city", "") or ""


def register() -> None:
    from src.jefrey.ports import registry

    registry.default("tool_audit", SqlToolAudit)
    registry.default("tool_metrics", PrometheusToolMetrics)
    registry.default("approvals", HumanApprovalGate)
    registry.default("output_guard", ContentGuard)
    registry.default("prefs", TodayPrefs)
