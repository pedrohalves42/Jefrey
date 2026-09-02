"""tests/test_p5_audit_fallback.py — P5-05 audit fallback drill (DDIA cap3, CIPHER-025/010)

3 testes sem Postgres real (tmp_path isolado, mock get_settings).
SWE at Google cap14: teste como regressao, nao infra.
"""
from __future__ import annotations

import json
import pathlib
import py_compile


def test_audit_redact_before_json():
    """Redact antes de json + segunda camada redact_pii(raw) — DDIA cap3."""
    txt = pathlib.Path("src/jefrey/core/audit.py").read_text(encoding="utf-8")
    assert "_redact_detail" in txt and "detail_redacted" in txt, "sem _redact_detail"
    assert txt.find("_redact_detail") < txt.find("detail_json"), "redact ordem errada: deve vir antes de detail_json"
    assert "redact_pii(raw)" in txt, "segunda camada redact_pii(raw) ausente no fallback"


def test_fallback_file_redact(tmp_path):
    """_write_fallback redige PII (sk-, email, cpf) → [REDACTED] per linha jsonl."""
    from unittest.mock import MagicMock, patch

    from src.jefrey.core.audit import AuditLogger

    fallback = tmp_path / "fallback.jsonl"
    mock_settings = MagicMock()
    mock_settings.api.audit_fallback_path = str(fallback)
    with patch("src.jefrey.core.config.get_settings", return_value=mock_settings):
        AuditLogger()._write_fallback(
            thread_id="t1",
            tool_name="x",
            actor_role="user",
            risk="LOW",
            decision="allow",
            reason=None,
            approval_id=None,
            approval_decision=None,
            source="agent",
            detail={"pii": "sk-abc123XYZ45678901234567890 email a@b.com cpf 123.456.789-00"},
            error="drill",
            user_id="u1",
        )
    txt = fallback.read_text(encoding="utf-8")
    assert "[REDACTED]" in txt, "redact nao aplicado"
    assert "sk-abc123" not in txt and "a@b.com" not in txt and "123.456.789" not in txt, "PII vazou"
    rec = json.loads(txt.strip().splitlines()[0])
    assert "ts" in rec and "audit_error" in rec and rec["thread_id"] == "t1"


def test_fallback_user_id_consistency(tmp_path):
    """user_id None → 'system' consistente (Axiom #2)."""
    from unittest.mock import MagicMock, patch

    from src.jefrey.core.audit import AuditLogger

    fallback = tmp_path / "fallback.jsonl"
    mock_settings = MagicMock()
    mock_settings.api.audit_fallback_path = str(fallback)
    with patch("src.jefrey.core.config.get_settings", return_value=mock_settings):
        AuditLogger()._write_fallback(
            thread_id="t1",
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


def test_drill_py_compile_and_no_user_id():
    """drill_audit_fallback.py compila + sem user_id em labelnames + FAIL-CLOSED."""
    p = pathlib.Path("scripts/drill_audit_fallback.py")
    py_compile.compile(str(p), doraise=True)
    txt = p.read_text(encoding="utf-8")
    assert "FAIL-CLOSED" in txt and "sys.exit(2)" in txt, "sem FAIL-CLOSED"
    for line in txt.splitlines():
        if "labelnames" in line:
            assert "user_id" not in line, f"user_id em labelnames: {line}"
