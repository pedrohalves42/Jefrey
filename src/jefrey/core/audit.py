"""Audit Log — gravação em Postgres (P4, CIPHER-010).

Substitui o log estruturado em docker logs por tabela ``audit_logs``. Toda
decisão de ferramenta (allow/deny/hitl) e desfecho de aprovação (approved/
rejected/expired) é persistida para auditoria forense.

Resiliência: se o Postgres estiver indisponível, registra warning (não quebra o
fluxo da ferramenta) — mas o alvo é que o log canônico seja o banco, não o stdout.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class AuditLogger:
    def log(
        self, *, thread_id: str, tool_name: str, actor_role: str,
        risk: str, decision: str, reason: str | None = None,
        approval_id: str | None = None, approval_decision: str | None = None,
        source: str = "agent", detail: dict | None = None,
    ) -> None:
        try:
            from src.jefrey.core.db import get_db
            from src.jefrey.core.models import AuditLog

            with get_db() as s:
                s.add(AuditLog(
                    id=uuid.uuid4(),
                    thread_id=thread_id,
                    tool_name=tool_name,
                    actor_role=actor_role,
                    risk=risk,
                    decision=decision,
                    reason=reason,
                    approval_id=approval_id,
                    approval_decision=approval_decision,
                    source=source,
                    detail_json=dict(detail or {}),
                ))
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "audit: falha ao gravar no Postgres (thread=%s tool=%s decision=%s): %s",
                thread_id, tool_name, decision, type(e).__name__,
            )


_logger = AuditLogger()


def get_audit_logger() -> AuditLogger:
    return _logger


def audit_tool_call(
    *, thread_id: str, tool_name: str, actor_role: str, risk: str,
    decision: str, reason: str | None = None, approval_id: str | None = None,
    approval_decision: str | None = None, source: str = "agent", detail: dict | None = None,
) -> None:
    _logger.log(
        thread_id=thread_id, tool_name=tool_name, actor_role=actor_role, risk=risk,
        decision=decision, reason=reason, approval_id=approval_id,
        approval_decision=approval_decision, source=source, detail=detail,
    )
