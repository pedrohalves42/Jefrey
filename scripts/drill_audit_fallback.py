#!/usr/bin/env python3
"""
scripts/drill_audit_fallback.py — P5-05 audit fallback drill (DDIA cap3 Store+Retrieve)
Axiom #6 PERSISTENCIA REAL + CIPHER-025 dual-write + CIPHER-010 audit visivel
DDIA cap3 p.70-95: WAL local quando Postgres cai — fallback nunca silencia.
Isolado: tmp_path/tempfile sem sujar data/audit_fallback.jsonl real; idempotente.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

# Ensure src on path for 'jefrey' import when run as script (Axiom #6 isolamento)
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _is_prod() -> bool:
    return os.getenv("JEFREY_ENV", "dev") == "prod"


def _require_not_prod(force: bool) -> None:
    if _is_prod() and not force:
        print("FAIL-CLOSED: JEFREY_ENV=prod — recusa drill sem --force (Axiom #1)", file=sys.stderr)
        sys.exit(2)


def drill_audit_fallback(tmp_path: Path | None = None, force: bool = False) -> Path:
    """Forca AuditLogger._write_fallback sem Postgres; verifica redact_pii."""
    _require_not_prod(force)
    from unittest.mock import MagicMock, patch

    from src.jefrey.core.audit import AuditLogger

    fallback = tmp_path / "audit_fallback.jsonl" if tmp_path else Path(tempfile.mktemp(suffix=".jsonl"))
    fallback.parent.mkdir(parents=True, exist_ok=True)

    mock_settings = MagicMock()
    mock_settings.api.audit_fallback_path = str(fallback)

    logger = AuditLogger()
    detail = {
        "msg": "token sk-abc123XYZ45678901234567890 email test@example.com cpf 123.456.789-00 bearer Bearer abc.def.ghi",
        "nested": {"email": "pii@exemplo.com"},
    }
    with patch("src.jefrey.core.config.get_settings", return_value=mock_settings):
        logger._write_fallback(
            thread_id="t-drill",
            tool_name="memory.search",
            actor_role="user",
            risk="LOW",
            decision="allow",
            reason=None,
            approval_id=None,
            approval_decision=None,
            source="agent",
            detail=detail,
            error="ConnectionRefusedError: postgres down (drill)",
            user_id="u-drill",
        )

    content = fallback.read_text(encoding="utf-8")
    assert "[REDACTED]" in content, "redact_pii nao aplicado no fallback"
    assert "sk-abc123" not in content, "PII sk vazou"
    assert "test@example.com" not in content, "PII email vazou"
    assert "123.456.789" not in content, "PII cpf vazou"
    assert "t-drill" in content and "u-drill" in content, "thread/user ausente"
    assert "audit_error" in content, "audit_error ausente"
    # JSON valido por linha
    for line in content.strip().splitlines():
        rec = json.loads(line)
        assert "ts" in rec and "thread_id" in rec, "record sem ts/thread_id"
    print(f"[drill] audit fallback OK -> {fallback} ({len(content)} bytes, redact OK)")
    return fallback


def drill_audit_user_id_none(tmp_path: Path | None = None, force: bool = False) -> Path:
    """Verifica user_id None -> 'system' consistente."""
    _require_not_prod(force)
    from unittest.mock import MagicMock, patch

    from src.jefrey.core.audit import AuditLogger

    fallback = (tmp_path / "fallback_none.jsonl") if tmp_path else Path(tempfile.mktemp(suffix="_none.jsonl"))
    fallback.parent.mkdir(parents=True, exist_ok=True)
    mock_settings = MagicMock()
    mock_settings.api.audit_fallback_path = str(fallback)
    with patch("src.jefrey.core.config.get_settings", return_value=mock_settings):
        AuditLogger()._write_fallback(
            thread_id="t-none",
            tool_name="x",
            actor_role="user",
            risk="LOW",
            decision="deny",
            reason="r",
            approval_id=None,
            approval_decision=None,
            source="agent",
            detail={},
            error="e",
            user_id=None,
        )
    rec = json.loads(fallback.read_text(encoding="utf-8").strip().splitlines()[0])
    assert rec["user_id"] == "system", f"user_id None -> {rec['user_id']} != system"
    print(f"[drill] user_id None -> system OK -> {fallback}")
    return fallback


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Drill audit fallback (DDIA cap3, CIPHER-025)")
    ap.add_argument("--force", action="store_true", help="permite em JEFREY_ENV=prod")
    ap.add_argument("--cleanup", action="store_true", help="remove tmp file apos drill")
    ap.add_argument("--all", action="store_true", help="roda drill + user_id none")
    ap.add_argument("mode", nargs="?", default="run", choices=["run", "help", "none"])
    args = ap.parse_args()
    _require_not_prod(args.force)
    if args.mode == "help":
        ap.print_help()
        sys.exit(0)
    if args.all:
        p1 = drill_audit_fallback(force=args.force)
        p2 = drill_audit_user_id_none(force=args.force)
        print(f"[drill] all DONE [{p1.name}, {p2.name}]")
        if args.cleanup:
            p1.unlink(missing_ok=True)
            p2.unlink(missing_ok=True)
    elif args.mode == "none":
        p = drill_audit_user_id_none(force=args.force)
        if args.cleanup:
            p.unlink(missing_ok=True)
    else:
        p = drill_audit_fallback(force=args.force)
        if args.cleanup:
            p.unlink(missing_ok=True)
