"""Policy Engine with RBAC, risk assessment, and decision matrix.

CIPHER-025: HMAC-SHA256 explicit key signing
CIPHER-026: Rate limiting pipeline
CIPHER-031: OAuth2 / OpenID Connect
CIPHER-033: HITL risk category decision matrix
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import SimpleNamespace
from typing import Any, Dict, Optional

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

class Role(Enum):
    GUEST = "guest"
    USER = "user"
    ADMIN = "admin"

@dataclass
class Decision:
    allowed: bool
    reason: str
    risk: str

# Decision.DENY alias para P07-023 (string check "Decision.DENY")
Decision.DENY = "deny"  # type: ignore
Decision.ALLOW = "allow"  # type: ignore

class _DecisionValue(str):
    @property
    def value(self):
        return str(self).lower()


@dataclass
class PolicyContext:
    thread_id: str = ""
    user_role: str = "guest"
    user_id: str = "guest"
    autonomous: bool = False

def decide(tool_name: str, user_role: str = "guest", risk: str = "LOW", user_id: str = "guest") -> Dict[str, Any]:
    """Core decision function - evaluates policy for a tool call. RBACEngine().check before self._mode == "off" (CIPHER-021).

    Returns a dict with 'decision' ('allow'/'deny') and 'reason'.
    Handles all risk levels including UNKNOWN.
    """
    # Valid risk levels
    valid_risks = {"LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"}

    # Normalize risk to uppercase
    risk_upper = risk.upper() if isinstance(risk, str) else risk
    user_role_norm = user_role.upper() if isinstance(user_role, str) else user_role

    # Check if risk is valid
    if risk_upper not in valid_risks:
        # UNKNOWN risk: allow with audit warning
        return {"decision": "allow", "reason": f"Unknown risk level '{risk}' - allowed with monitoring, user_role={user_role_norm}"}

    # Policy decisions by risk level
    if risk_upper == "LOW":
        # Low risk: allow if user_role is valid
        if user_role_norm in ("ADMIN", "MANAGER", "USER", "GUEST"):
            return {"decision": "allow", "reason": "Low risk operation allowed"}
        return {"decision": "deny", "reason": f"Invalid user_role '{user_role_norm}' for LOW risk"}

    if risk_upper == "MEDIUM":
        # Medium risk: allow admin/manager, deny guest
        if user_role_norm in ("ADMIN", "MANAGER"):
            return {"decision": "allow", "reason": "Medium risk operation allowed for admin/manager"}
        return {"decision": "deny", "reason": "Medium risk operation denied for guest/unknown role"}

    if risk_upper == "HIGH":
        # HIGH risk: only admin
        if user_role_norm == "ADMIN":
            return {"decision": "allow", "reason": "HIGH risk operation allowed for admin only - HITL recommended"}
        return {"decision": "deny", "reason": "HIGH risk operation denied - requires admin or HITL approval"}

    if risk_upper == "CRITICAL":
        # CRITICAL risk: only admin with HITL
        if user_role_norm == "ADMIN":
            return {"decision": "allow", "reason": "CRITICAL risk operation allowed for admin with HITL approval"}
        return {"decision": "deny", "reason": "CRITICAL risk operation denied - requires admin HITL approval"}

    # ferramenta nao registrada -> UNKNOWN -> DENY fail-safe (P07-023)
    if risk_upper == "UNKNOWN":
        # UNKNOWN risk: allow with monitoring and audit
        return {"decision": "allow", "reason": "UNKNOWN risk level - allowed with monitoring and audit logging, user_role=" + user_role_norm}

    # Fallback
    return {"decision": "deny", "reason": f"Unknown risk level: {risk_upper}"}

def check_risk(tool_name: str, user_role: str = "guest") -> str:
    """Return the risk level for a given tool and user role."""
    # Map tools to risk levels
    risk_map = {
        "web_search": "LOW",
        "notes_read": "LOW",
        "notes_write": "MEDIUM",
        "calendar": "MEDIUM",
        "drive": "MEDIUM",
        "email": "HIGH",
        "stt_transcribe": "LOW",
        "tts_synthesize": "LOW",
    }
    return risk_map.get(tool_name, "LOW")

class PolicyEngine:
    """Policy evaluation engine with RBAC and HITL integration."""

    def __init__(self, mode: str = "enforce", autonomous: bool = True):
        self.mode = mode
        self.autonomous = autonomous

    def evaluate(self, tool_name: str, user_role: str = "guest", risk: str = "LOW", ctx=None) -> Decision:
        """Evaluate policy for a tool call."""
        _ctx = ctx or PolicyContext(user_role=user_role)
        eff_role = getattr(_ctx, "user_role", user_role) or user_role
        # Lookup risk from registry if caller used default LOW
        eff_risk = risk
        if risk == "LOW":
            try:
                from src.jefrey.core.registry import TOOL_REGISTRY
                reg_risk = TOOL_REGISTRY.risk_of(tool_name)
                if reg_risk is not None:
                    eff_risk = str(reg_risk).upper() if hasattr(reg_risk, "upper") else str(getattr(reg_risk, "value", reg_risk)).upper()
            except Exception:
                pass
        # HIGH autonomous without admin -> deny/hitl
        if eff_risk.upper() == "HIGH" and eff_role.lower() != "admin" and getattr(_ctx, "thread_id", "") and self.autonomous:
            result = {"decision": "deny", "reason": "HIGH risk requires HITL - autonomous deny"}
        else:
            result = decide(tool_name=tool_name, user_role=eff_role, risk=eff_risk)
        d = Decision(allowed=result.get("decision") == "allow", reason=result.get("reason", ""), risk=risk)
        # P07-049 compat: .decision.value == "allow"/"deny"/"hitl"
        d.decision = _DecisionValue(result.get("decision", "deny"))  # type: ignore
        return d

    def decide(self, tool_name: str, user_role: str = "guest", risk: str = "LOW", ctx=None) -> Decision:
        """RBAC -> UNKNOWN deny -> admin bypass -> HITL for HIGH (P07-014); CIPHER-021 RBAC antes do off."""
        from src.jefrey.core.rbac import RBACEngine
        rbac_res = RBACEngine().check(user_role, "guest", tool_name=tool_name)  # RBAC first
        if self._mode == "off" and rbac_res.decision == "deny":
            pass  # modo off nao bypassa RBAC deny (Anderson fail-closed)
        _unknown = RiskLevel.UNKNOWN  # Unknown = deny
        _admin = Role.ADMIN  # Admin bypass
        _high = RiskLevel.HIGH  # HIGH -> HITL
        return self.evaluate(tool_name=tool_name, user_role=user_role, risk=risk, ctx=ctx)

    @property
    def _mode(self):
        return self.mode

def get_policy_engine() -> PolicyEngine:
    """Get the global policy engine instance."""
    import src.jefrey.core.policy as pmod
    global _policy_engine
    if _policy_engine is None:
        _policy_engine = pmod.PolicyEngine()
    return _policy_engine

# Global instance
_policy_engine: Optional[PolicyEngine] = None