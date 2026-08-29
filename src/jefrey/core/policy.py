"""Policy Engine + HITL + Auditoria (Fase P2 — fecha critérios SEG/OBS).

Classificação de risco por ferramenta e decisão ALLOW / HITL / DENY.
Em modo autônomo (sem humano no loop), HIGH/CRITICAL são BLOQUEADOS (DENY) e o
pedido é registrado na tabela `approvals` (HITL futuro, P4/P5). Todo call de ferramenta
é auditado via logging estruturado (JSON).

Alvo arquitetural: Jefrey (cérebro) → Policy Engine → ALLOW | HITL → Audit Log.
"""
from __future__ import annotations

import enum
import logging
import uuid
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Decision(str, enum.Enum):
    ALLOW = "allow"
    HITL = "hitl"
    DENY = "deny"


@dataclass
class RunContext:
    """Contexto passado ao runtime do agente (e às ferramentas via RunContextWrapper)."""

    thread_id: str = "default"
    user_role: str = "user"  # admin | user | guest (RBAC, P4)
    autonomous: bool = True  # se False, tudo vira HITL


@dataclass
class PolicyContext:
    thread_id: str = "default"
    user_role: str = "user"
    autonomous: bool = True


@dataclass
class PolicyResult:
    decision: Decision
    risk: RiskLevel
    reason: str
    approval_id: str | None = None


_AUTO_APPROVE: set[RiskLevel] = {RiskLevel.LOW, RiskLevel.MEDIUM}


class PolicyEngine:
    """Avalia o risco de uma ferramenta e decide ALLOW / HITL / DENY."""

    def __init__(
        self,
        auto_approve: set[RiskLevel] | None = None,
        mode: str = "enforce",
        autonomous: bool = True,
        approval_store: Any | None = None,
    ):
        self._auto = auto_approve or _AUTO_APPROVE
        self._mode = mode
        self._autonomous = autonomous
        self._approval_store = approval_store

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def autonomous(self) -> bool:
        return self._autonomous

    def risk_of(self, tool_name: str) -> RiskLevel:
        """Classifica o risco pela convenção de nome da ferramenta (fail-safe: HIGH).

        BUG-P3a-01: as ferramentas do SkillRegistry usam nomes por função
        (save_note, search_notes, create_workflow, ...) que NÃO seguem o prefixo
        notes_/web_search_/automation_. Com a classificação anterior, TODAS as ferramentas
        reais caiam em 'desconhecido = HIGH' e eram bloqueadas em modo enforce — o gateway
        barraria todas as ferramentas legítimas. Reclassificado por semântica:
        leitura/busca/memória = LOW; automação/workflow/deleção = MEDIUM;
        email/calendar/gmail/destrutivas = HIGH. O fixo durável (risco declarado por
        ferramenta na skill) fica para P4 (Security/guardrails).
        """
        n = (tool_name or "").lower()
        # Alto risco: integrações externas destrutivas / envio
        if n.startswith(("email_", "calendar_", "gmail_")):
            return RiskLevel.HIGH
        if any(k in n for k in ("rm_rf", "delete_system", "shell_exec", "os_exec", "run_command")):
            return RiskLevel.HIGH
        # Médio: automação / workflows / deleções
        if n.startswith("automation_") or "workflow" in n or n.startswith("plan_") or n == "extract":
            return RiskLevel.MEDIUM
        if n.startswith("notes_delete") or n.startswith("delete_"):
            return RiskLevel.MEDIUM
        # Baixo: leitura / busca / memória pessoal
        if n.startswith("notes_") or n.startswith("web_search") or n == "memory_search":
            return RiskLevel.LOW
        if "note" in n or "search" in n or "memory" in n:
            return RiskLevel.LOW
        # Desconhecido = alto (princípio do menor privilégio)
        return RiskLevel.HIGH

    def decide(
        self, tool_name: str, args: dict | None = None, ctx: PolicyContext | None = None
    ) -> PolicyResult:
        ctx = ctx or PolicyContext()
        if self._mode == "off":
            return PolicyResult(Decision.ALLOW, self.risk_of(tool_name), "policy desligada")
        risk = self.risk_of(tool_name)

        # admin bypass (RBAC completo em P4)
        if ctx.user_role == "admin":
            return PolicyResult(Decision.ALLOW, risk, "admin bypass")

        if risk == RiskLevel.CRITICAL:
            return self._hitl(tool_name, args, risk, ctx, "crítico exige aprovação humana")
        if risk == RiskLevel.HIGH:
            return self._hitl(tool_name, args, risk, ctx, "alto risco requer HITL")

        if self._mode == "audit":
            return PolicyResult(Decision.ALLOW, risk, f"{risk.value}: modo auditoria (apenas logado)")
        if risk in self._auto:
            return PolicyResult(Decision.ALLOW, risk, f"{risk.value}: auto-aprovado")
        return PolicyResult(Decision.ALLOW, risk, "default allow")

    def _hitl(self, tool_name, args, risk, ctx, reason) -> PolicyResult:
        approval_id = None
        if self._approval_store is not None:
            try:
                approval_id = self._approval_store.create(
                    thread_id=ctx.thread_id,
                    tool_name=tool_name,
                    arguments=args or {},
                    risk_level=risk.value,
                    reason=reason,
                )
            except Exception as e:  # noqa: BLE001
                logger.error("falha ao registrar approval: %s", e)
        logger.warning(
            "HITL tool=%s risk=%s thread=%s approval=%s",
            tool_name, risk.value, ctx.thread_id, approval_id,
        )
        # Sem humano disponível (autônomo): bloqueia por segurança.
        if self._autonomous or self._mode == "enforce":
            return PolicyResult(
                Decision.DENY, risk,
                f"{reason} (autônomo: bloqueado sem humano)", approval_id,
            )
        return PolicyResult(Decision.HITL, risk, reason, approval_id)

    def audit(self, tool_name: str, decision: PolicyResult, ctx: PolicyContext | None = None) -> None:
        ctx = ctx or PolicyContext()
        logger.info(
            "tool_call tool=%s risk=%s decision=%s reason=%s thread=%s approval=%s",
            tool_name, decision.risk.value, decision.decision.value, decision.reason,
            ctx.thread_id, decision.approval_id,
        )


class ApprovalStore:
    """Persiste pedidos de aprovação HITL na tabela `approvals` (Postgres)."""

    def create(
        self, thread_id: str, tool_name: str, arguments: dict,
        risk_level: str, reason: str | None = None,
    ) -> str:
        from src.jefrey.core.db import get_db
        from src.jefrey.core.models import Approval

        aid = str(uuid.uuid4())
        with get_db() as s:
            s.add(Approval(
                id=uuid.UUID(aid),
                thread_id=thread_id,
                tool_name=tool_name,
                arguments_json=dict(arguments or {}),
                risk_level=risk_level,
                status="pending",
                reason=reason,
            ))
        logger.info("approval criado id=%s tool=%s thread=%s", aid, tool_name, thread_id)
        return aid

    def list_pending(self, thread_id: str | None = None) -> list[dict]:
        from src.jefrey.core.db import get_db
        from src.jefrey.core.models import Approval

        with get_db() as s:
            q = s.query(Approval)
            if thread_id:
                q = q.filter(Approval.thread_id == thread_id)
            rows = q.filter(Approval.status == "pending").all()
            return [
                {
                    "id": str(r.id), "tool_name": r.tool_name,
                    "risk_level": r.risk_level, "status": r.status,
                    "thread_id": r.thread_id,
                }
                for r in rows
            ]

    def decide(self, approval_id: str, decision: str, decided_by: str | None = None) -> bool:
        from src.jefrey.core.db import get_db
        from src.jefrey.core.models import Approval
        from sqlalchemy import func

        with get_db() as s:
            r = s.get(Approval, uuid.UUID(approval_id))
            if r is None:
                return False
            r.status = decision
            r.decided_by = decided_by
            r.decided_at = func.now()
            return True


_POLICY: "PolicyEngine | None" = None


def get_policy_engine() -> PolicyEngine:
    """Singleton do PolicyEngine (com ApprovalStore Postgres)."""
    global _POLICY
    if _POLICY is None:
        from src.jefrey.core.config import get_settings

        cfg = get_settings().policy
        _POLICY = PolicyEngine(
            mode=cfg.mode,
            autonomous=cfg.autonomous,
            approval_store=ApprovalStore(),
        )
    return _POLICY
