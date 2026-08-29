"""Audit Log — gravação em Postgres (P4, CIPHER-010).

Substitui o log estruturado em docker logs por tabela ``audit_logs``. Toda
decisão de ferramenta (allow/deny/hitl) e desfecho de aprovação (approved/
rejected/expired) é persistida para auditoria forense.

Resiliência (CIPHER-025): se o Postgres estiver indisponível, NÃO silencia — registra
erro e faz dual-write para arquivo de fallback local (JEFREY_API__AUDIT_FALLBACK_PATH)
com alerta. O log canônico é o banco; o fallback garante rastro forense mesmo em queda.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
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
            # CIPHER-025: falha NÃO é silenciosa — erro visível + dual-write de fallback.
            logger.error(
                "audit: FALHA ao gravar no Postgres (thread=%s tool=%s decision=%s): %s",
                thread_id, tool_name, decision, type(e).__name__,
            )
            self._write_fallback(
                thread_id=thread_id, tool_name=tool_name, actor_role=actor_role,
                risk=risk, decision=decision, reason=reason, approval_id=approval_id,
                approval_decision=approval_decision, source=source, detail=detail,
                error=f"{type(e).__name__}: {e}",
            )

    def _write_fallback(
        self, *, thread_id: str, tool_name: str, actor_role: str, risk: str,
        decision: str, reason: str | None, approval_id: str | None,
        approval_decision: str | None, source: str, detail: dict | None, error: str,
    ) -> None:
        """CIPHER-025: grava o evento de auditoria em arquivo local quando o Postgres falha.

        Comportamento definido (não silencioso): preserva o rastro forense e emite alerta.
        """
        try:
            from src.jefrey.core.config import get_settings

            path = get_settings().api.audit_fallback_path
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            record = {
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "thread_id": thread_id, "tool_name": tool_name, "actor_role": actor_role,
                "risk": risk, "decision": decision, "reason": reason,
                "approval_id": approval_id, "approval_decision": approval_decision,
                "source": source, "detail": detail or {}, "audit_error": error,
            }
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            logger.warning("audit: fallback local gravado em %s (Postgres indisponível)", path)
        except Exception as fe:  # noqa: BLE001
            logger.error("audit: FALHA também no fallback local (%s): %s", path, type(fe).__name__)


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
