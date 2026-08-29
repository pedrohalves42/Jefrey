"""ToolRegistry — registro explícito de ferramentas (P4, Decisão 3 — Opção B).

Cada ferramenta exposta pelo Jefrey DEVE ser registrada aqui com risco e papel
mínimo explícitos. O PolicyEngine consulta este registry; ferramentas NÃO
registradas recebem risco UNKNOWN e são bloqueadas por padrão (fail-safe) —
fecha BUG-P3a-01 (risco não é mais inferido por heurística de nome) e satisfaz
AXIOM #5 (ferramenta nova sem risco declarado é bloqueada).

Servidores MCP externos (MCPClient, Opção B) registram suas ferramentas aqui
via ``MCPClient.register_explicit()`` — não há descoberta automática de tools.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from src.jefrey.core.rbac import Role, as_role

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolRegistration:
    name: str
    risk: "object"            # RiskLevel (importado lazy p/ evitar ciclo)
    required_role: Role = Role.USER
    description: str = ""
    server: "str | None" = None
    source: str = "skill"     # skill | mcp | integration | test
    external: bool = False

    @property
    def risk_value(self) -> str:
        return getattr(self.risk, "value", str(self.risk))


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolRegistration] = {}

    def register(
        self,
        *,
        name: str,
        risk: "object",
        required_role: "str | Role" = Role.USER,
        description: str = "",
        server: "str | None" = None,
        source: str = "skill",
        external: bool = False,
        overwrite: bool = True,
    ) -> ToolRegistration:
        role = as_role(required_role)
        if not overwrite and name in self._tools:
            return self._tools[name]
        reg = ToolRegistration(
            name=name, risk=risk, required_role=role,
            description=description, server=server, source=source, external=external,
        )
        self._tools[name] = reg
        return reg

    def get(self, name: str) -> "ToolRegistration | None":
        return self._tools.get(name)

    def risk_of(self, name: str) -> "object | None":
        reg = self._tools.get(name)
        return reg.risk if reg else None

    def required_role_of(self, name: str) -> "Role | None":
        reg = self._tools.get(name)
        return reg.required_role if reg else None

    def all(self) -> list[ToolRegistration]:
        return list(self._tools.values())

    def registered_names(self) -> set[str]:
        return set(self._tools)


TOOL_REGISTRY = ToolRegistry()

_registered = False


def register_default_tools() -> None:
    """Registra explicitamente todas as ferramentas conhecidas do Jefrey.

    Idempotente. Chamado por ``get_policy_engine()`` e por ``build_server()``/agente
    para garantir que o PolicyEngine tenha risco/papel de toda ferramenta exposta.
    Novas ferramentas DEVEM ser adicionadas aqui (ou registradas no ToolRegistry)
    antes de serem expostas — caso contrário serão UNKNOWN (bloqueadas).
    """
    global _registered
    if _registered:
        return
    from src.jefrey.core.policy import RiskLevel

    R = RiskLevel
    reg = TOOL_REGISTRY

    # --- notes (memória pessoal) ---
    reg.register(name="save_note", risk=R.LOW, required_role=Role.USER, source="skill")
    reg.register(name="update_note", risk=R.LOW, required_role=Role.USER, source="skill")
    reg.register(name="delete_note", risk=R.LOW, required_role=Role.USER, source="skill")
    reg.register(name="search_notes", risk=R.LOW, required_role=Role.GUEST, source="skill")
    reg.register(name="list_notes", risk=R.LOW, required_role=Role.GUEST, source="skill")
    reg.register(name="get_note", risk=R.LOW, required_role=Role.GUEST, source="skill")

    # --- web_search (leitura externa) ---
    reg.register(name="search", risk=R.LOW, required_role=Role.GUEST, source="skill")
    reg.register(name="search_news", risk=R.LOW, required_role=Role.GUEST, source="skill")
    reg.register(name="extract", risk=R.LOW, required_role=Role.GUEST, source="skill")

    # --- automation (escrita/execução) ---
    reg.register(name="create_workflow", risk=R.MEDIUM, required_role=Role.USER, source="skill")
    reg.register(name="run_workflow", risk=R.MEDIUM, required_role=Role.USER, source="skill")
    reg.register(name="delete_workflow", risk=R.MEDIUM, required_role=Role.USER, source="skill")
    reg.register(name="plan_task", risk=R.MEDIUM, required_role=Role.USER, source="skill")
    reg.register(name="list_workflows", risk=R.LOW, required_role=Role.GUEST, source="skill")
    reg.register(name="get_workflow", risk=R.LOW, required_role=Role.GUEST, source="skill")

    # --- calendar (Google, externo) ---
    reg.register(name="list_events", risk=R.LOW, required_role=Role.GUEST, source="skill")
    reg.register(name="find_free_slots", risk=R.LOW, required_role=Role.GUEST, source="skill")
    reg.register(name="get_calendar_list", risk=R.LOW, required_role=Role.GUEST, source="skill")
    reg.register(name="create_event", risk=R.HIGH, required_role=Role.USER, source="skill")
    reg.register(name="update_event", risk=R.HIGH, required_role=Role.USER, source="skill")
    reg.register(name="delete_event", risk=R.HIGH, required_role=Role.USER, source="skill")

    # --- email (Gmail, externo) ---
    reg.register(name="list_messages", risk=R.LOW, required_role=Role.GUEST, source="skill")
    reg.register(name="get_message", risk=R.LOW, required_role=Role.GUEST, source="skill")
    reg.register(name="search_messages", risk=R.LOW, required_role=Role.GUEST, source="skill")
    reg.register(name="list_labels", risk=R.LOW, required_role=Role.GUEST, source="skill")
    reg.register(name="modify_labels", risk=R.MEDIUM, required_role=Role.USER, source="skill")
    reg.register(name="send_message", risk=R.HIGH, required_role=Role.USER, source="skill")
    reg.register(name="reply_message", risk=R.HIGH, required_role=Role.USER, source="skill")

    # --- integration stubs (gateway MCP) ---
    reg.register(name="email_send", risk=R.HIGH, required_role=Role.USER, source="integration")
    reg.register(name="calendar_create", risk=R.HIGH, required_role=Role.USER, source="integration")

    _registered = True
    logger.info("ToolRegistry: %d ferramentas registradas", len(reg.registered_names()))
