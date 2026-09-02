"""
CIPHER-034: Skill Base Versioning

Provides version detection, compatibility checking, and deprecation management
for skill packages. Supports Axiom #7: Skill base versioning.

Version format: MAJOR.MINOR.PATCH (semantic versioning)
Compatibility: MINOR/PATCH are backward compatible, MAJOR requires HITL approval
Deprecation: Skills beyond max_deprecated_count trigger warnings

FASE 4 B1 — semver real via packaging.version + tomllib (stdlib py3.12)
6 princípios: FAIL-CLOSED, ISOLAMENTO, SEM STUB, PERSISTÊNCIA, CRIPTO, LEAST PRIVILEGE
SWE at Google cap.14 — MINOR auto, MAJOR HITL
"""

import logging
import warnings
logger = logging.getLogger(__name__)
import re
import pathlib
from typing import Optional, Dict, Any, Tuple

try:
    from packaging.version import Version, InvalidVersion  # type: ignore
except ImportError:  # fallback se packaging ausente (dev deve instalar packaging>=24.0)
    Version = None  # type: ignore
    InvalidVersion = Exception  # type: ignore

try:
    import tomllib  # py3.11+ stdlib
except ModuleNotFoundError:
    tomllib = None  # type: ignore


def get_skill_version(skill_name: str, skill_metadata: Optional[Dict[str, Any]] = None) -> str:
    """Get the version of a skill.

    Order: skill_metadata["version"] -> pyproject.toml ([tool.poetry] or [project]) -> registry -> 0.1.0
    Validates via packaging.version.Version + strict MAJOR.MINOR.PATCH regex.
    Only warns on invalid format, not on missing (avoid noisy warn in prod).

    Args:
        skill_name: Name of the skill
        skill_metadata: Optional metadata dict; if not provided, attempts to load

    Returns:
        Version string in MAJOR.MINOR.PATCH format, or '0.1.0' as default
    """
    default_version = "0.1.0"

    # 1) metadata explicito
    if skill_metadata and "version" in skill_metadata:
        v = str(skill_metadata["version"]).strip()
        try:
            if Version is not None:
                Version(v)
            if re.match(r"^\d+\.\d+\.\d+$", v):
                return v
            warnings.warn(f"Invalid version format for {skill_name}: {v} (expected MAJOR.MINOR.PATCH)", UserWarning, stacklevel=2)
            return default_version
        except InvalidVersion:
            warnings.warn(f"Invalid version format for {skill_name}: {v}", UserWarning, stacklevel=2)
            return default_version

    # 2) pyproject.toml — fonte canonica (poetry ou pep621)
    try:
        pp = pathlib.Path("pyproject.toml")
        if pp.exists() and tomllib is not None:
            data = tomllib.loads(pp.read_text(encoding="utf-8"))
            v = None
            # poetry: [tool.poetry] version
            try:
                v = data.get("tool", {}).get("poetry", {}).get("version")
            except Exception:
                v = None
            if not v:
                try:
                    v = data.get("project", {}).get("version")
                except Exception:
                    v = None
            if v:
                vs = str(v).strip()
                if Version is not None:
                    Version(vs)
                if re.match(r"^\d+\.\d+\.\d+$", vs):
                    return vs
    except Exception as _e:
        logger.debug("version fallback: %s", _e)
        pass

    # 3) registry fallback (ToolRegistration.version)
    try:
        from src.jefrey.core.registry import get_registry  # type: ignore

        reg = get_registry()
        tools = getattr(reg, "_tools", {})
        meta = tools.get(skill_name)
        if meta is not None:
            v = None
            if isinstance(meta, dict):
                v = meta.get("version")
            else:
                v = getattr(meta, "version", None)
            if v:
                vs = str(v).strip()
                if Version is not None:
                    Version(vs)
                if re.match(r"^\d+\.\d+\.\d+$", vs):
                    return vs
    except Exception as _e:
        logger.debug("version fallback: %s", _e)
        pass

    return default_version


def check_skill_compatibility(
    current_version: str,
    required_version: str,
    strict: bool = False,
) -> Tuple[bool, str]:
    """Check if current_version is compatible with required_version.

    CIPHER-034: Skill compatibility checking per semantic versioning via packaging.version.
    B1b FIX: MAJOR increase => False (HITL), not True.

    Compatibility rules (SWE at Google 14):
    - Same version: compatible
    - Same major, cur < req: compatible (MINOR/PATCH backward compat), strict => False
    - Different major, cur < req: NOT compatible, requires HITL (False)
    - cur > req: downgrade not allowed (False)

    Returns:
        (is_compatible, reason)
    """
    # packaging path (preferido)
    if Version is not None:
        try:
            cur = Version(current_version)
            req = Version(required_version)
        except InvalidVersion as e:
            return False, f"Invalid version format: {e}"
        if cur > req:
            return False, "Version downgrade not allowed"
        if cur == req:
            return True, f"Compatible: same version {cur}"
        # cur < req
        if cur.major == req.major:
            if strict:
                return False, "Version change requires HITL approval (strict mode)"
            return True, f"Compatible: same major {cur.major}. MINOR/PATCH backward compatible"
        # major diferente => breaking
        return False, f"MAJOR version increase {cur} -> {req} requires HITL approval"

    # fallback sem packaging (str.split manual) — mantem compat mas deprecated
    warnings.warn("packaging not installed, using fallback split — install packaging>=24.0", UserWarning, stacklevel=2)
    try:
        current_parts = [int(x) for x in current_version.split(".")]
        required_parts = [int(x) for x in required_version.split(".")]
    except ValueError as e:
        return False, f"Invalid version format: {e}"
    while len(current_parts) < 3:
        current_parts.append(0)
    while len(required_parts) < 3:
        required_parts.append(0)
    curr_maj, curr_min, curr_pat = current_parts
    req_maj, req_min, req_pat = required_parts
    if curr_maj > req_maj or (curr_maj == req_maj and curr_min > req_min) or (curr_maj == req_maj and curr_min == req_min and curr_pat > req_pat):
        return False, "Version downgrade not allowed"
    if curr_maj == req_maj:
        if strict:
            return False, "Version change requires HITL approval (strict mode)"
        return True, f"Compatible: same major version {curr_maj}. MINOR/PATCH changes are backward compatible"
    if curr_maj < req_maj:
        return False, f"MAJOR version increase {curr_maj}.{curr_min}.{curr_pat} -> {req_maj}.{req_min}.{req_pat} requires HITL approval"
    return False, "Unexpected version comparison result"


def get_deprecated_skills(max_deprecated: int = 3) -> Dict[str, str]:
    """Get skills that have exceeded the maximum deprecated count.

    CIPHER-034: reads registry _tools deprecated flag.
    Warns if len > max_deprecated (SWE at Google).

    Returns:
        Dict skill_name -> version for deprecated skills
    """
    out: Dict[str, str] = {}
    try:
        from src.jefrey.core.registry import get_registry  # type: ignore

        reg = get_registry()
        tools = getattr(reg, "_tools", {})
        for name, meta in tools.items():
            deprecated = False
            ver = "0.1.0"
            if isinstance(meta, dict):
                deprecated = bool(meta.get("deprecated", False))
                ver = str(meta.get("version", "0.1.0"))
            else:
                deprecated = bool(getattr(meta, "deprecated", False))
                ver = str(getattr(meta, "version", "0.1.0"))
            if deprecated:
                out[name] = ver
    except Exception as _e:
        logger.debug("version fallback: %s", _e)
        pass
    if len(out) > max_deprecated:
        warnings.warn(f"{len(out)} deprecated skills > max {max_deprecated}", UserWarning, stacklevel=2)
    return out


def should_auto_upgrade(skill_name: str, current_version: str) -> Tuple[bool, Optional[str]]:
    """Check if a skill should be auto-upgraded.

    Only MINOR/PATCH within same MAJOR auto-upgrades (SWE at Google 14).
    MAJOR available => False + latest version (requires HITL), not auto.

    Returns:
        (should_upgrade, new_version) — new_version is latest even when should_upgrade is False (for HITL prompt)
    """
    # valida current
    if Version is not None:
        try:
            cur = Version(current_version)
        except InvalidVersion:
            return False, None
    else:
        # fallback: tenta parse simples
        try:
            [int(x) for x in current_version.split(".")]
            cur = None  # type: ignore
        except Exception:
            return False, None

    latest = None
    latest_str: Optional[str] = None
    try:
        from src.jefrey.core.registry import get_registry  # type: ignore

        reg = get_registry()
        tools = getattr(reg, "_tools", {})
        meta = tools.get(skill_name)
        if meta is not None:
            v = None
            if isinstance(meta, dict):
                v = meta.get("latest_version") or meta.get("version")
            else:
                v = getattr(meta, "latest_version", None) or getattr(meta, "version", None)
            if v:
                latest_str = str(v).strip()
                if Version is not None:
                    latest = Version(latest_str)
                else:
                    latest = latest_str  # type: ignore
    except Exception as _e:
        logger.debug("version fallback: %s", _e)
        pass

    if latest is None or latest_str is None:
        return False, None

    # compara
    if Version is not None:
        assert isinstance(latest, Version)
        assert isinstance(cur, Version)
        if latest <= cur:
            return False, None
        if latest.major == cur.major:
            return True, str(latest)
        return False, str(latest)
    # fallback sem packaging
    try:
        cur_parts = [int(x) for x in current_version.split(".")]
        lat_parts = [int(x) for x in latest_str.split(".")]
        while len(cur_parts) < 3:
            cur_parts.append(0)
        while len(lat_parts) < 3:
            lat_parts.append(0)
        if lat_parts <= cur_parts:
            return False, None
        if lat_parts[0] == cur_parts[0]:
            return True, latest_str
        return False, latest_str
    except Exception:
        return False, None


def format_version_change_message(
    from_version: str,
    to_version: str,
    requires_approval: bool = False,
) -> str:
    """Format a human-readable message about a skill version change."""
    lines = [f"Skill version change: {from_version} -> {to_version}"]
    if requires_approval:
        lines.append("HITL approval required: MAJOR version change (breaking changes)")
    else:
        lines.append("Compatible: MINOR/PATCH change (backward compatible)")
    return "\n".join(lines)
