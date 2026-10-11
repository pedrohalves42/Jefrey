"""Atalho de compatibilidade do RBAC: regras em domain/rbac.py; aqui so a leitura da configuracao (papel do servico)."""
from src.jefrey.domain.rbac import *  # noqa: F401,F403
from src.jefrey.domain.rbac import Role, resolve_effective_role  # noqa: F401


def resolve_role(preferred: "str | Role | None" = None) -> Role:
    """Resolve o papel efetivo SERVER-SIDE (CIPHER-022) a partir de ``service_role``/``allowed_roles`` da configuracao."""
    from src.jefrey.core.config import get_settings

    cfg = get_settings().mcp
    return resolve_effective_role(preferred, cfg.allowed_roles, cfg.service_role)
