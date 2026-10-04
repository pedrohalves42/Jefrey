"""Lista as skills e ferramentas realmente carregadas no servidor."""
from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/skills", tags=["skills"])


def _risk_of(tool_name: str) -> str | None:
    try:
        from src.jefrey.core.registry import get_tool_risk
        r = get_tool_risk(tool_name)
        return str(r).lower() if r else None
    except Exception:
        return None


def describe_skills() -> list[dict]:
    from src.jefrey.skills import load_skills, skill_registry

    load_skills()  # idempotente
    out: list[dict] = []
    for meta in skill_registry.list_skills():
        skill = skill_registry.get_skill(meta.name)
        tools = []
        try:
            tools = [
                {"name": t.name, "description": (t.description or "").strip().split("\n")[0][:160], "risk": _risk_of(t.name)}
                for t in (skill.get_tools() if skill else [])
            ]
        except Exception as e:  # uma skill quebrada nao derruba a listagem
            logger.warning("skills: falha ao listar ferramentas de %s: %s", meta.name, e)
        out.append({
            "name": meta.name,
            "description": meta.description,
            "version": meta.version,
            "tags": list(meta.tags),
            "requires_auth": bool(meta.requires_auth),
            "tools": tools,
        })
    return out


@router.get("")
async def list_skills():
    skills = describe_skills()
    return {"skills": skills, "count": len(skills), "tool_count": sum(len(s["tools"]) for s in skills)}
