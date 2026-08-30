"""HITL — Approval Manager (P4, Decisão 2 — Opção A).

Gerencia o ciclo de vida das aprovações Human-in-the-Loop na tabela ``approvals``:
criar, listar pendentes, decidir (approve/reject) e expirar (approval_ttl).

RISCO ATIVO (P4): o polling no agent loop precisa de teto. ``approval_ttl``
(padrão 30 min, JEFREY_HITL__APPROVAL_TTL) define o prazo; após expirar, a
aprovação transiciona para ``expired`` e a ferramenta é NEGADA automaticamente.
"""
from __future__ import annotations

import asyncio
import enum
import logging
import time
import uuid
import datetime
from typing import Any

from src.jefrey.core.rbac import as_role  # noqa: F401  (mantém API simétrica)
from src.jefrey.core.metrics import APPROVALS_CREATED, APPROVALS_DECIDED

logger = logging.getLogger(__name__)


class ApprovalDecision(str, enum.Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ApprovalManager:
    def __init__(self, ttl: "float | None" = None) -> None:
        from src.jefrey.core.config import get_settings

        self._ttl = float(ttl if ttl is not None else get_settings().hitl.approval_ttl)

    # ----- escrita -----
    def create(
        self, *, thread_id: str, tool_name: str, arguments: dict,
        risk_level: str, reason: str | None = None,
        created_by: str | None = None, server: str | None = None,
        user_id: str = "system",
    ) -> str:
        from src.jefrey.core.db import get_db
        from src.jefrey.core.models import Approval
        from sqlalchemy import func

        aid = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc)
        expires = now + datetime.timedelta(seconds=self._ttl)
        with get_db() as s:
            s.add(Approval(
                id=uuid.UUID(aid),
                user_id=user_id,
                thread_id=thread_id,
                tool_name=tool_name,
                arguments_json=dict(arguments or {}),
                risk_level=risk_level,
                status="pending",
                reason=reason,
                created_by=created_by,
                expires_at=expires,
            ))
        logger.info(
            "approval criado id=%s tool=%s thread=%s user=%s expires_em=%.0fs",
            aid, tool_name, thread_id, user_id, self._ttl,
        )
        APPROVALS_CREATED.labels(tool_name=tool_name, risk_level=risk_level).inc()
        return aid

    def decide(self, approval_id: str, decision: str, decided_by: str | None = None,
               user_id: str | None = None) -> bool:
        from src.jefrey.core.db import get_db
        from src.jefrey.core.models import Approval
        from sqlalchemy import func

        d = str(decision).lower()
        if d not in ("approved", "rejected"):
            raise ValueError(f"decisão inválida: {decision}")
        _tool_name = ""
        with get_db() as s:
            r = s.get(Approval, uuid.UUID(approval_id))
            if r is None or r.status != "pending":
                return False
            # SECURITY: ownership check — só o dono pode decidir
            if user_id is not None and r.user_id != user_id:
                logger.warning(
                    "decide negado: approval_id=%s pertence a user=%s, não a user=%s",
                    approval_id, r.user_id, user_id,
                )
                return False
            _tool_name = r.tool_name  # captura antes do session close
            r.status = d
            r.decided_by = decided_by
            r.decided_at = func.now()
        logger.info("approval %s -> %s por %s (user=%s)", approval_id, d, decided_by, user_id)
        APPROVALS_DECIDED.labels(decision=d, tool_name=_tool_name).inc()
        return True

    def expire_due(self) -> int:
        """Marca aprovações pendentes vencidas como 'expired'. Retorna qtd."""
        from src.jefrey.core.db import get_db
        from src.jefrey.core.models import Approval

        now = datetime.datetime.now(datetime.timezone.utc)
        count = 0
        with get_db() as s:
            rows = s.query(Approval).filter(
                Approval.status == "pending",
                Approval.expires_at.isnot(None),
                Approval.expires_at < now,
            ).all()
            for r in rows:
                r.status = "expired"
                r.decided_at = now
                APPROVALS_DECIDED.labels(decision="expired", tool_name=r.tool_name).inc()
                count += 1
        if count:
            logger.info("approval(s) expirada(s): %d", count)
        return count

    # ----- leitura -----
    def get(self, approval_id: str) -> "dict | None":
        from src.jefrey.core.db import get_db
        from src.jefrey.core.models import Approval

        with get_db() as s:
            r = s.get(Approval, uuid.UUID(approval_id))
            if r is None:
                return None
            return self._row_to_dict(r)

    def get_pending(self, thread_id: str | None = None, user_id: str | None = None) -> list[dict]:
        from src.jefrey.core.db import get_db
        from src.jefrey.core.models import Approval

        self.expire_due()
        with get_db() as s:
            q = s.query(Approval).filter(Approval.status == "pending")
            if thread_id:
                q = q.filter(Approval.thread_id == thread_id)
            # SECURITY: filtra por user_id para isolamento multi-tenant
            if user_id is not None:
                q = q.filter(Approval.user_id == user_id)
            return [self._row_to_dict(r) for r in q.all()]

    @staticmethod
    def _row_to_dict(r) -> dict:
        return {
            "id": str(r.id),
            "user_id": r.user_id,
            "thread_id": r.thread_id,
            "tool_name": r.tool_name,
            "arguments_json": r.arguments_json,
            "risk_level": r.risk_level,
            "status": r.status,
            "reason": r.reason,
            "created_by": r.created_by,
            "decided_by": r.decided_by,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "decided_at": r.decided_at.isoformat() if r.decided_at else None,
        }

    # ----- polling (usado pelo agent loop) -----
    async def wait_for_decision(
        self, approval_id: str, timeout: "float | None" = None,
        poll_interval: "float | None" = None,
    ) -> str:
        """Aguarda a decisão humana (ou expiração) por até `timeout` segundos.

        Retorna: 'approved' | 'rejected' | 'expired' | 'not_found'.
        Se o prazo esgota sem decisão, a aprovação é marcada 'expired' e o
        resultado é 'expired' (o agente então NEGA a ferramenta automaticamente).
        """
        from src.jefrey.core.config import get_settings

        timeout = float(timeout if timeout is not None else self._ttl)
        poll_interval = float(
            poll_interval if poll_interval is not None else get_settings().hitl.poll_interval
        )
        deadline = time.monotonic() + timeout
        while True:
            self.expire_due()
            row = self.get(approval_id)
            if row is None:
                return "not_found"
            status = row["status"]
            if status == "approved":
                return "approved"
            if status == "rejected":
                return "rejected"
            if status == "expired":
                return "expired"
            if time.monotonic() >= deadline:
                self.expire_due()
                return "expired"
            await asyncio.sleep(poll_interval)
