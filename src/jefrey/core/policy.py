"""Policy Engine + RBAC + HITL + Auditoria (P4).

Classificação de risco EXPLÍCITA por ferramenta (ToolRegistry) — não mais
heurística de nome (BUG-P3a-01 fechado). RBAC (3 papéis) aplicado ANTES da
decisão de risco. HITL via ApprovalManager (tabela approvals, com expires_at).
Auditoria via audit_logs (Postgres, CIPHER-010).

Alvo arquitetural: Jefrey (cérebro) -> RBAC -> Policy Engine -> ALLOW | HITL -> Audit Log.
"""
from __future__ import annotations

import enum
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from src.jefrey.core.rbac import Role, as_role, RBACEngine
from src.jefrey.core.registry import TOOL_REGISTRY, register_default_tools

logger = logging.getLogger(__name__)


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"   # ferramenta não registrada -> bloqueada por padrão (AXIOM #5)


class Decision(str, enum.Enum):
    ALLOW = "allow"
    HITL = "hitl"
    DENY = "deny"


@dataclass
class RunContext:
    """Contexto passado ao runtime do agente (compat)."""
    thread_id: str = "default"
    user_role: str = "user"  # admin | user | guest (RBAC, P4)
    autonomous: bool = True  # se False, tudo vira HITL


@dataclass
class PolicyContext:
    thread_id: str = "default"
    user_role: str = "user"   # admin | user | guest (RBAC, P4)
    user_id: str = "system"   # SECURITY: multi-tenant isolation
    autonomous: bool = True   # True => gateway (sem humano): HIGH/CRITICAL => DENY
                              # False => agente (humano no loop): HIGH/CRITICAL => HITL (aguarda)


@dataclass
class PolicyResult:
    decision: Decision
    risk: RiskLevel
    reason: str
    approval_id: str | None = None


_AUTO_APPROVE: set[RiskLevel] = {RiskLevel.LOW, RiskLevel.MEDIUM}


class PolicyEngine:
    """Avalia o risco (declarado) de uma ferramenta e decide ALLOW / HITL / DENY."""

    def __init__(self, mode: str = "enforce", autonomous: bool = True, approval_manager: Any | None = None):
        self._mode = mode
        self._autonomous = autonomous
        self._approval_manager = approval_manager

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def autonomous(self) -> bool:
        return self._autonomous

    def risk_of(self, tool_name: str) -> RiskLevel:
        """Risco EXPLÍCITO vindo do ToolRegistry. Não registrado => UNKNOWN (bloqueado)."""
        register_default_tools()
        rk = TOOL_REGISTRY.risk_of(tool_name)
        return rk if rk is not None else RiskLevel.UNKNOWN

    def decide(self, tool_name, args=None, ctx=None) -> PolicyResult:
        ctx = ctx or PolicyContext()
        risk = self.risk_of(tool_name)

        # --- 1) RBAC (SEMPRE, antes de tudo — CIPHER-021) ---
        # 'off' desativa só o PolicyEngine de risco; RBAC roda sempre (um guest NUNCA
        # executa ferramenta MEDIUM/HIGH mesmo com policy desligada).
        required = TOOL_REGISTRY.required_role_of(tool_name) or Role.USER
        rbac_res = RBACEngine().check(ctx.user_role, required, tool_name)
        if rbac_res.decision == "deny":
            return PolicyResult(Decision.DENY, risk, rbac_res.reason)

        # --- 2) risco nao declarado => bloqueia (fail-safe, AXIOM #5) ---
        # G1: UNKNOWN antes de rate-limit -> nao conta quota nem gasta EVAL pra ferramenta inexistente.
        if risk == RiskLevel.UNKNOWN:
            return PolicyResult(
                Decision.DENY, risk, "ferramenta nao registrada no ToolRegistry (risco desconhecido)",
            )

        # --- 1b) Rate-limit (P1.2 E1, CIPHER-025, Anderson least privilege) ---
        # Fail-open degradado: se rate-limit deny -> DENY (nao bypass), mas se Redis fora -> fallback local.
        # Diferente de auth/HITL (fail-closed), rate-limit degrada para in-memory sem quebrar request.
        # G2 INTENCIONAL: admin sofre rate-limit (infra protection). Se isentar admin, mover bypass antes.
        # G3 INTENCIONAL: rate-limit roda mesmo com mode=off (defense in depth, Anderson).
        #                 Se quiser respeitar off, mover este bloco apos o check de off.
        try:
            from src.jefrey.core.rate_limit import get_rate_limiter

            _rl = get_rate_limiter()
            _rl_dec = _rl.is_allowed(ctx.user_id, tool_name)
            if _rl_dec == "deny":
                return PolicyResult(Decision.DENY, risk, "rate limit exceeded")
        except Exception:
            pass  # fail-open para rate-limit apenas (nao afeta RBAC/HITL)

        if self._mode == "off":
            return PolicyResult(Decision.ALLOW, risk, "policy desligada (RBAC mantido)")

        # --- 3) admin bypass (AXIOM #4) ---
        if as_role(ctx.user_role) == Role.ADMIN:
            return PolicyResult(Decision.ALLOW, risk, "admin bypass")

        # --- 4) HITL para HIGH/CRITICAL ---
        if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            return self._hitl(tool_name, args, risk, ctx)

        # --- 5) LOW/MEDIUM ---
        if self._mode == "audit":
            return PolicyResult(Decision.ALLOW, risk, f"{risk.value}: modo auditoria (apenas logado)")
        if risk in _AUTO_APPROVE:
            return PolicyResult(Decision.ALLOW, risk, f"{risk.value}: auto-aprovado")
        return PolicyResult(Decision.ALLOW, risk, "default allow")

    def _hitl(self, tool_name, args, risk, ctx) -> PolicyResult:
        am = self._approval_manager
        if am is None:
            from src.jefrey.core.hitl import ApprovalManager

            am = ApprovalManager()
        approval_id = am.create(
            thread_id=ctx.thread_id, tool_name=tool_name, arguments=args or {},
            risk_level=risk.value, reason=f"{risk.value} requer aprovação humana",
            created_by=ctx.user_role, user_id=ctx.user_id,
        )
        logger.warning(
            "HITL tool=%s risk=%s thread=%s approval=%s",
            tool_name, risk.value, ctx.thread_id, approval_id,
        )
        if ctx.autonomous:
            # gateway autônomo: sem humano => bloqueia por segurança (approval registrado p/ análise).
            return PolicyResult(
                Decision.DENY, risk,
                f"{risk.value}: autônomo (sem humano no loop), bloqueado", approval_id,
            )
        # agente com humano no loop: retorna HITL para o executor aguardar a decisão REST.
        return PolicyResult(
            Decision.HITL, risk, f"{risk.value}: aguardando aprovação humana", approval_id,
        )

    def audit(self, tool_name, decision: PolicyResult, ctx=None) -> None:
        ctx = ctx or PolicyContext()
        from src.jefrey.core.audit import audit_tool_call

        audit_tool_call(
            thread_id=ctx.thread_id, tool_name=tool_name, actor_role=ctx.user_role,
            risk=decision.risk.value, decision=decision.decision.value,
            reason=decision.reason, approval_id=decision.approval_id, source="policy",
        )


_POLICY: "PolicyEngine | None" = None


def get_policy_engine() -> PolicyEngine:
    """Singleton do PolicyEngine (com ToolRegistry populado + ApprovalManager)."""
    global _POLICY
    if _POLICY is None:
        from src.jefrey.core.config import get_settings

        cfg = get_settings().policy
        register_default_tools()
        _POLICY = PolicyEngine(mode=cfg.mode, autonomous=cfg.autonomous)
    return _POLICY
