"""
CIPHER-034: Skill Base Versioning

Exports for skill version detection, compatibility checking, and deprecation management.
Supports Axiom #7: Skill base versioning.
"""

from src.jefrey.skills.version import (
    get_skill_version,
    check_skill_compatibility,
    get_deprecated_skills,
    should_auto_upgrade,
    format_version_change_message,
)

__all__ = [
    "get_skill_version",
    "check_skill_compatibility",
    "get_deprecated_skills",
    "should_auto_upgrade",
    "format_version_change_message",
]