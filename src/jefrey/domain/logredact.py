"""Tira chaves e tokens de qualquer linha de registro (o httpx registra a URL inteira, e algumas APIs pedem o token na URL)."""
from __future__ import annotations

import logging
import re

_SECRET = re.compile(r"((?:token|secret|access_token|api[_-]?key|key|password|code_verifier|refresh_token)=)[^&\s\"']+", re.I)
_BEARER = re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=-]{8,}", re.I)


def scrub(text: str) -> str:
    return _BEARER.sub(r"\1***", _SECRET.sub(r"\1***", text))


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = scrub(record.getMessage())  # formata primeiro (o token pode vir nos argumentos) e so depois limpa
            record.args = None
        except Exception:  # nunca derruba o registro
            pass
        return True


def install() -> None:
    """Liga o filtro nos registradores que mostram enderecos (idempotente)."""
    for name in ("httpx", "httpcore", "uvicorn.access", "src.jefrey"):
        lg = logging.getLogger(name)
        if not any(isinstance(f, RedactFilter) for f in lg.filters):
            lg.addFilter(RedactFilter())
