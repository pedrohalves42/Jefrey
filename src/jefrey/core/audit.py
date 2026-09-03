"""Audit Log — gravacao em Postgres (P4, CIPHER-010).

Substitui o log estruturado em docker logs por tabela ``audit_logs``. Toda
decisao de ferramenta (allow/deny/hitl) e desfecho de aprovacao (approved/
rejected/expired) eh persistida para auditoria forense.

Resiliencia (CIPHER-025): se o Postgres estiver indisponivel, NAO silencia — registra
erro e faz dual-write para arquivo de fallback local (JEFREY_API__AUDIT_FALLBACK_PATH)
com alerta. O log canonico eh o banco; o fallback garante rastro forense mesmo em queda.
Fail-closed: detail eh redigido (redact_pii) antes de json.dumps para nao vazar PII.
HPP cap2: orjson + lru_cache 1024 memoize; manter redact_pii 2 camadas.
""" 
from __future__ import annotations

import datetime
import functools
import json
import logging
import os
import re
import uuid
from typing import Any

logger = logging.getLogger(__name__)

try:
    import orjson as _orjson
    _HAS_ORJSON = True
except Exception:
    _orjson = None  # type: ignore
    _HAS_ORJSON = False

_PII_RE = re.compile(
    r"(sk-[a-zA-Z0-9]{20,}|Bearer\s+[a-zA-Z0-9._\-]+|[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}|cpf\s*\d{3}\.?\d{3}\.?\d{3}-?\d{2})",
    re.IGNORECASE,
)


@functools.lru_cache(maxsize=1024)
def redact_pii(s: str) -> str:
    return _PII_RE.sub("[REDACTED]", s)


def _redact_detail(detail: dict | None) -> dict:
    if not detail:
        return {}
    out: dict[str, Any] = {}
    for k, v in detail.items():
        if isinstance(v, str):
            out[k] = redact_pii(v)
        elif isinstance(v, dict):
            out[k] = _redact_detail(v)  # type: ignore[arg-type]
        else:
            out[k] = v
    return out


class AuditLogger:
    def log(
        self, *, thread_id: str, tool_name: str, actor_role: str,
        risk: str, decision: str, reason: str | None = None,
        approval_id: str | None = None, approval_decision: str | None = None,
        source: str = "agent", detail: dict | None = None,
        user_id: str | None = None,
    ) -> None:
        # redact antes de persistir (evita PII em detail_json)
        detail_redacted = _redact_detail(detail)
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
                    detail_json=dict(detail_redacted),
                    user_id=user_id or "system",
                ))
                s.commit()
        except Exception as e:  # noqa: BLE001
            # CIPHER-025: falha NAO eh silenciosa — erro visivel + dual-write de fallback.
            logger.error(
                "audit: FALHA ao gravar no Postgres (thread=%s tool=%s decision=%s): %s",
                thread_id, tool_name, decision, type(e).__name__,
            )
            self._write_fallback(
                thread_id=thread_id, tool_name=tool_name, actor_role=actor_role,
                risk=risk, decision=decision, reason=reason, approval_id=approval_id,
                approval_decision=approval_decision, source=source, detail=detail_redacted,
                error=f"{type(e).__name__}: {e}",
                user_id=user_id,
            )

    def _write_fallback(
        self, *, thread_id: str, tool_name: str, actor_role: str, risk: str,
        decision: str, reason: str | None, approval_id: str | None,
        approval_decision: str | None, source: str, detail: dict | None, error: str,
        user_id: str | None = None,
    ) -> None:
        """CIPHER-025: grava o evento de auditoria em arquivo local quando o Postgres falha.""" 
        path = ""
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
                "user_id": user_id or "system",
            }
            # HPP cap2: orjson + redact_pii deterministico; fallback json se orjson ausente
            if _HAS_ORJSON:
                raw = _orjson.dumps(record, option=_orjson.OPT_SORT_KEYS).decode("utf-8")  # type: ignore
                raw = redact_pii(raw)
            else:
                raw = json.dumps(record, ensure_ascii=False, default=str, sort_keys=True)
                raw = redact_pii(raw)
            with open(path, "a", encoding="utf-8") as f:
                f.write(raw + "\n")
            logger.warning("audit: fallback local gravado em %s (Postgres indisponivel)", path)
        except Exception as fe:  # noqa: BLE001
            logger.error("audit: FALHA tambem no fallback local (%s): %s", path, type(fe).__name__)


_logger = AuditLogger()

def get_audit_logger() -> AuditLogger:
    return _logger

def audit_tool_call(
    *, thread_id: str, tool_name: str, actor_role: str, risk: str,
    decision: str, reason: str | None = None, approval_id: str | None = None,
    approval_decision: str | None = None, source: str = "agent", detail: dict | None = None,
    user_id: str | None = None,
) -> None:
    _logger.log(
        thread_id=thread_id, tool_name=tool_name, actor_role=actor_role, risk=risk,
        decision=decision, reason=reason, approval_id=approval_id,
        approval_decision=approval_decision, source=source, detail=detail,
        user_id=user_id,
    )
