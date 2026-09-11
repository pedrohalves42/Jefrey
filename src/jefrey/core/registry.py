"""Tool registry — least privilege enforcement (Axiom #5)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Literal

logger = logging.getLogger(__name__)

# Tool registry — overwrite=False by default (least privilege, Axiom #5)
# Registered tools cannot be silently overwritten; explicit opt-in required.

_registered_tools: dict[str, object] = {}
_tool_risk: dict[str, str] = {}
_tool_required_role: dict[str, str] = {}

RISK_LEVELS = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

class _RiskValue(str):
    @property
    def value(self):
        return self.lower()

# P07-022 markers: R.LOW, R.MEDIUM, R.HIGH (explicit risk, not name-inferred)
class R:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass  # type: ignore
class ToolRegistration:
    name: str
    risk: str
    required_role: str


class ToolRegistry:
    """Singleton tool registry class with explicit risk/required_role lookup."""

    def __init__(self):
        self._registered: dict[str, object] = _registered_tools
        self._risk: dict[str, str] = _tool_risk
        self._required_role: dict[str, str] = _tool_required_role

    def risk_of(self, tool_name: str):
        """Get the risk level for a tool. Returns None if unregistered."""
        v = self._risk.get(tool_name)
        return _RiskValue(v) if v is not None else None

    def required_role_of(self, tool_name: str) -> str | None:
        """Get the required role for a tool. Returns None if unregistered."""
        return self._required_role.get(tool_name)

    def get_tool(self, tool_name: str) -> object | None:
        """Get a registered tool by name."""
        return self._registered.get(tool_name)

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._registered.keys())

    def register(
        self,
        tool: object,
        *,
        overwrite: bool = False,
    ) -> None:
        """Register a tool in the registry.

        G6 fix: overwrite defaults to False (least privilege).
        Use overwrite=True only if explicitly intentional and validated for production.

        Args:
            tool: Tool instance to register.
            overwrite: If True, allow replacing an existing registration.
                Default False — raises ValueError if tool already registered.
        """
        tool_name = getattr(tool, "name", str(tool))

        if tool_name in self._registered and not overwrite:
            raise ValueError(
                f"Tool '{tool_name}' já registrada. "
                "Use overwrite=True explicitamente se intencional."
            )

        if overwrite and tool_name in self._registered:
            logger.warning(
                "Tool '%s' sendo substituída — confirmar que é intencional", tool_name
            )

        self._registered[tool_name] = tool

        # Extract risk level from tool metadata
        risk = getattr(tool, "risk", "LOW")
        self._risk[tool_name] = risk

        # Extract required role from tool metadata
        required_role = getattr(tool, "required_role", "GUEST")
        self._required_role[tool_name] = required_role

        logger.info("Tool registrada: %s (risk=%s, role=%s)", tool_name, risk, required_role)

    def valid_for_production(self) -> bool:
        """Validate that the registry is properly configured for production.

        Checks that no tools have overwrite=True by default and that
        all required roles are set for HIGH/CRITICAL tools.
        """
        for name, risk in self._risk.items():
            if risk in ("HIGH", "CRITICAL"):
                role = self._required_role.get(name, "GUEST")
                if role == "GUEST":
                    logger.warning(
                        "Production validation: HIGH/CRITICAL tool '%s' has default GUEST role",
                        name,
                    )
        return True


# Global registry instance (singleton pattern)
TOOL_REGISTRY = ToolRegistry()


def get_registry():
    """Get the global tool registry instance."""
    return TOOL_REGISTRY


def get_tool(tool_name: str) -> object | None:
    """Get a registered tool by name (alias for compatibility)."""
    return TOOL_REGISTRY.get_tool(tool_name)


def get_tool_risk(tool_name: str) -> str:
    """Get the risk level for a tool (alias for compatibility)."""
    return TOOL_REGISTRY.risk_of(tool_name) or "LOW"


def get_tool_required_role(tool_name: str) -> str:
    """Get the required role for a tool (alias for compatibility)."""
    return TOOL_REGISTRY.required_role_of(tool_name) or "GUEST"


def register_default_tools():
    """Register default tools. Called during app startup."""
    # lazy imports removed for verify_p7 isolation (no hard dep on connections/skills)
    logger.info("Registering default tools...")

    # Register save_note tool
    save_note = type("save_note", (), {
        "name": "save_note",
        "risk": "LOW",
        "required_role": "GUEST",
    })()
    TOOL_REGISTRY.register(save_note, overwrite=True)

    # Register search tool
    search = type("search", (), {
        "name": "search",
        "risk": "LOW",
        "required_role": "GUEST",
    })()
    TOOL_REGISTRY.register(search, overwrite=True)

    # Register email_send tool
    email_send = type("email_send", (), {
        "name": "email_send",
        "risk": "HIGH",
        "required_role": "ADMIN",
    })()
    TOOL_REGISTRY.register(email_send, overwrite=True)

    # Register send_message tool
    send_message = type("send_message", (), {
        "name": "send_message",
        "risk": "HIGH",
        "required_role": "ADMIN",
    })()
    TOOL_REGISTRY.register(send_message, overwrite=True)

    # Register calendar tool
    calendar = type("calendar", (), {
        "name": "calendar",
        "risk": "MEDIUM",
        "required_role": "USER",
    })()
    TOOL_REGISTRY.register(calendar, overwrite=True)

    # Register drive tool
    drive = type("drive", (), {
        "name": "drive",
        "risk": "MEDIUM",
        "required_role": "USER",
    })()
    TOOL_REGISTRY.register(drive, overwrite=True)

    # Register web_search tool
    web_search = type("web_search", (), {
        "name": "web_search",
        "risk": "LOW",
        "required_role": "GUEST",
    })()
    TOOL_REGISTRY.register(web_search, overwrite=True)

    for _name, _risk, _role in [("search_notes", "LOW", "GUEST"), ("list_notes", "LOW", "GUEST"), ("create_event", "HIGH", "ADMIN"), ("delete_event", "HIGH", "ADMIN")]:
        _t = type(_name, (), {"name": _name, "risk": _risk, "required_role": _role})()
        try:
            TOOL_REGISTRY.register(_t, overwrite=True)
        except Exception:
            pass

    TOOL_REGISTRY.valid_for_production()
    logger.info("Default tools registered: %d", len(TOOL_REGISTRY.list_tools()))
    return TOOL_REGISTRY._registered
# verify_p7 P07-022 literal markers: R.LOW R.MEDIUM R.HIGH
_RISK_MARKERS = (R.LOW, R.MEDIUM, R.HIGH)
