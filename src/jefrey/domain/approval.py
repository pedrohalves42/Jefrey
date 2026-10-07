"""Texto curto que mostra a pessoa O QUE ela esta aprovando (para, quem e o que sera enviado). Regra pura; nada de segredo."""
from __future__ import annotations

from typing import Any, Mapping


def _line(s: Any, n: int) -> str:
    return " ".join(str(s or "").split())[:n]


def approval_detail(tool: str, args: Mapping[str, Any]) -> str:
    """Resumo dos argumentos de uma ferramenta de risco, so para as que enviam algo a outra pessoa. Vazio = sem detalhe."""
    if tool == "wa_send_message":
        return f"Para {_line(args.get('contact'), 60)}: “{_line(args.get('message'), 280)}”"
    if tool in ("send_message", "reply_message"):
        to = _line(args.get("to") or args.get("recipient"), 80)
        subject = _line(args.get("subject"), 80)
        body = _line(args.get("body") or args.get("message") or args.get("text"), 200)
        parts = [f"Para {to}" if to else "", f"Assunto: {subject}" if subject else "", f"“{body}”" if body else ""]
        return " · ".join(p for p in parts if p)
    return ""
