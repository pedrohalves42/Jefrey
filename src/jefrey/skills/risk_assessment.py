"""
CIPHER-032: Skill Risk Assessment

Maps registered skills to risk levels and required roles for PolicyEngine integration.
Provides dynamic risk assessment based on tool characteristics and configuration.

Axiom #2: Session isolation between tenants - risk assessment uses user_id from context.
Axiom #7: Skill base versioning - risk levels can vary by skill version.
"""

from typing import Optional, Dict, Any

from src.jefrey.core.policy import PolicyResult, PolicyContext, RiskLevel


def assess_skill_risk(
    tool_name: str,
    tool_config: Optional[Dict[str, Any]] = None,
    ctx: Optional[PolicyContext] = None,
) -> RiskLevel:
    """
    Assess the risk level of a skill/tool based on its characteristics.

    CIPHER-032: Skill risk assessment per tool_name and configuration.

    Args:
        tool_name: Name of the tool/skill being assessed
        tool_config: Optional configuration dict for the tool
        ctx: Optional PolicyContext for user_id-aware assessment

    Returns:
        RiskLevel enum value (LOW, MEDIUM, HIGH, CRITICAL)

    Examples:
        assess_skill_risk("social_post_create") -> RiskLevel.MEDIUM
        assess_skill_risk("financial_analysis") -> RiskLevel.HIGH
    """
    ctx = ctx or PolicyContext()

    # CIPHER-032: Default risk mapping based on tool name patterns
    # These mappings are reviewed and updated per Axiom #7 versioning
    _risk_map = {
        # LOW risk: read-only, no external calls, no user data modification
        "social_get_status": RiskLevel.LOW,
        "health_check": RiskLevel.LOW,
        "status_check": RiskLevel.LOW,
        # MEDIUM risk: write operations, external API calls, user-generated content
        "social_post_create": RiskLevel.MEDIUM,
        "social_post_schedule": RiskLevel.MEDIUM,
        "content_generate": RiskLevel.MEDIUM,
        "message_send": RiskLevel.MEDIUM,
        "workflow_execute": RiskLevel.MEDIUM,
        "note_write": RiskLevel.MEDIUM,
        # HIGH risk: sensitive data access, financial operations, legal documents
        "financial_analysis": RiskLevel.HIGH,
        "document_create": RiskLevel.HIGH,
        "legal_draft": RiskLevel.HIGH,
        "contract_review": RiskLevel.HIGH,
        "database_query": RiskLevel.HIGH,
        "data_export": RiskLevel.HIGH,
        # CRITICAL risk: admin operations, system configuration, multi-tenant access
        "admin_configure": RiskLevel.CRITICAL,
        "tenant_manage": RiskLevel.CRITICAL,
        "system_reset": RiskLevel.CRITICAL,
        "mass_delete": RiskLevel.CRITICAL,
    }

    # Check explicit config risk override
    if tool_config and "risk_level" in tool_config:
        try:
            return RiskLevel(tool_config["risk_level"])
        except ValueError:
            pass  # fallback to default mapping

    # Determine risk from tool name pattern
    risk = _risk_map.get(tool_name, RiskLevel.MEDIUM)  # default to MEDIUM if unknown

    # CIPHER-032: user_id-aware adjustment for multi-tenant isolation
    # If user_id is available and tool accesses user data, potentially elevate risk
    if ctx and ctx.user_id and ctx.user_id != "system":
        # Tools that access user-specific data get MEDIUM minimum if was LOW
        if risk == RiskLevel.LOW and _uses_user_data(tool_name):
            risk = RiskLevel.MEDIUM
        # Tools that modify user data get HIGH minimum if was MEDIUM
        if risk == RiskLevel.MEDIUM and _modifies_user_data(tool_name):
            risk = RiskLevel.HIGH

    return risk


def _uses_user_data(tool_name: str) -> bool:
    """Check if tool name indicates user data access."""
    user_data_patterns = [
        "user_",
        "profile_",
        "contact_",
        "social_",
        "note_",
        "memory_",
    ]
    return any(pattern in tool_name for pattern in user_data_patterns)


def _modifies_user_data(tool_name: str) -> bool:
    """Check if tool name indicates user data modification."""
    modify_patterns = [
        "write_",
        "create_",
        "update_",
        "delete_",
        "save_",
        "remove_",
    ]
    return any(pattern in tool_name for pattern in modify_patterns)


def get_required_role(risk_level: RiskLevel) -> str:
    """Get the minimum required role for a given risk level."""
    _role_map = {
        RiskLevel.LOW: "GUEST",
        RiskLevel.MEDIUM: "USER",
        RiskLevel.HIGH: "ADMIN",
        RiskLevel.CRITICAL: "ADMIN",
    }
    return _role_map.get(risk_level, "USER")


def get_risk_reason(tool_name: str, risk_level: RiskLevel) -> str:
    """Get human-readable reason for the risk assessment."""
    _reasons = {
        RiskLevel.LOW: "Read-only operation, no external calls, no user data modification",
        RiskLevel.MEDIUM: "Write operation or external API call, user content generation",
        RiskLevel.HIGH: "Sensitive data access, financial/legal operations, requires human review",
        RiskLevel.CRITICAL: "Admin/system operations, multi-tenant access, configuration changes",
    }
    return _reasons.get(risk_level, "Unknown risk level")