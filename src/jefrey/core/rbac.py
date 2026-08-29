"""RBAC — Controle de Acesso Baseado em Papéis (P4, Decisão 1 — Opção A).

3 papéis fixos (Jefrey é assistente pessoal, não multi-tenant):
  - guest : apenas leitura (ferramentas com required_role=guest)
  - user  : leitura + escrita pessoal (required_role <= user)
  - admin : tudo (bypass de RBAC e HITL)

A granularidade por ferramenta é obtida via ``required_role`` declarado em cada
registro do ToolRegistry (ver registry.py) — não precisamos do overhead de
permissões por ferramenta (Opção B) para o caso de uso pessoal.
"""
from __future__ import annotations

import enum
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class Role(str, enum.Enum):
    GUEST = "guest"
    USER = "user"
    ADMIN = "admin"


_ROLE_RANK = {Role.GUEST: 0, Role.USER: 1, Role.ADMIN: 2}


def as_role(value: "str | Role | None") -> Role:
    """Converte string / Role / None em Role (default user)."""
    if isinstance(value, Role):
        return value
    try:
        return Role(str(value or "user").lower())
    except ValueError:
        return Role.USER


def role_allowed(actor: Role, required: Role) -> bool:
    """True se o papel do ator é suficiente para o papel exigido pela ferramenta."""
    return _ROLE_RANK[actor] >= _ROLE_RANK[required]

def resolve_role(preferred: "str | Role | None" = None) -> Role:
    """Resolve o papel efetivo SERVER-SIDE (CIPHER-022).

    Mesmo padrão de ``_resolve_role`` do gateway MCP: a fonte de verdade é
    ``service_role`` (config); um papel preferido (ex.: header ``X-Jefrey-Role``)
    só é honrado se estiver em ``allowed_roles``. Nunca confia em papel vindo de
    payload de chamador — fecha a superfície de CIPHER-001 também no agent loop.
    """
    from src.jefrey.core.config import get_settings

    cfg = get_settings().mcp
    allowed = {as_role(r) for r in (cfg.allowed_roles or [])}
    pref = as_role(preferred)
    if pref in allowed:
        return pref
    return as_role(cfg.service_role)


@dataclass
class RBACResult:
    decision: str          # "allow" | "deny"
    actor_role: Role
    required_role: Role
    reason: str


class RBACEngine:
    """Verifica se um ator pode usar uma ferramenta dado o papel exigido."""

    def check(
        self,
        actor_role: "str | Role",
        required_role: "str | Role",
        tool_name: str = "",
    ) -> RBACResult:
        actor = as_role(actor_role)
        required = as_role(required_role)
        if role_allowed(actor, required):
            return RBACResult(
                "allow", actor, required,
                f"papel {actor.value} >= exigido {required.value}",
            )
        return RBACResult(
            "deny", actor, required,
            f"papel {actor.value} insuficiente para '{tool_name}' "
            f"(exige >= {required.value})",
        )


def require_role(required_role: "str | Role", risk=None, source: str = "skill"):
    """Decorador leve que documenta o papel mínimo (e risco) de uma ferramenta.

    Armazena metadados em ``__jefrey_rbac__`` para inspeção por skill authors.
    O registro efetivo no ToolRegistry é feito centralmente por
    ``register_default_tools()`` — este decorador serve para documentação/descoberta.

        @require_role(Role.USER, risk=RiskLevel.MEDIUM)
        async def minha_tool(...): ...
    """
    required = as_role(required_role)

    def decorator(func):
        func.__jefrey_rbac__ = {
            "required_role": required,
            "risk": risk,
            "source": source,
        }
        return func

    return decorator
