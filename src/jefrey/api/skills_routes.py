"""Lista as skills e ferramentas realmente carregadas no servidor."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/skills", tags=["skills"])


def _risk_of(tool_name: str) -> str | None:
    try:
        from src.jefrey.core.tool_catalog import policy_for

        pol = policy_for(tool_name)  # a tabela de riscos que o agente realmente usa
        if pol is not None:
            return str(pol.risk).lower()
    except Exception as e:
        logger.debug("skills: risco pelo catalogo falhou (%s)", type(e).__name__)
    try:
        from src.jefrey.core.registry import get_tool_risk
        r = get_tool_risk(tool_name)
        return str(r).lower() if r else None
    except Exception:
        return None


def describe_skills() -> list[dict]:
    from src.jefrey.skills import load_skills, skill_registry

    from src.jefrey.core.skill_prefs import load_disabled

    load_skills()  # idempotente
    off = load_disabled()
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
            "enabled": meta.name not in off,
            "tools": tools,
        })
    return out


@router.get("")
async def list_skills(request: Request):
    skills = describe_skills()
    uid = getattr(request.state, "user_id", None)
    if uid:  # por usuario: diz o que falta conectar (ex.: conta Google)
        from src.jefrey.core.availability import unavailable_skills

        missing = unavailable_skills(uid)
        for sk in skills:
            sk["available"] = sk["name"] not in missing
            if sk["name"] in missing:
                sk["unavailable_reason"] = missing[sk["name"]]
    return {"skills": skills, "count": len(skills), "tool_count": sum(len(s["tools"]) for s in skills)}


class SkillToggle(BaseModel):
    enabled: bool


@router.put("/{name}")
async def toggle_skill(name: str, body: SkillToggle):
    """Liga ou desliga uma skill. Desligada, o agente nao enxerga nenhuma ferramenta dela."""
    from src.jefrey.core.skill_prefs import set_enabled
    from src.jefrey.skills import load_skills, skill_registry

    load_skills()
    if not skill_registry.is_loaded(name):
        raise HTTPException(status_code=404, detail="skill nao encontrada")
    set_enabled(name, body.enabled)
    return {"name": name, "enabled": body.enabled}
