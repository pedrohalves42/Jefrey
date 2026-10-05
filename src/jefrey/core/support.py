"""Relatorio "Algo deu errado": um .zip para mandar ao suporte, SEM segredos.

Conteudo: versao e sistema, o FINAL do registro (ja limpo) e um estado simples (sim/nao) das conexoes. Nunca inclui cofre, chaves,
arquivos de credenciais, memorias nem conversas. A pessoa decide se e quando envia: o Jefrey nunca manda sozinho.
"""
from __future__ import annotations

import io
import json
import logging
import os
import platform
import re
import zipfile
from datetime import datetime
from pathlib import Path

from src.jefrey.core.logredact import scrub

logger = logging.getLogger(__name__)

MAX_LINES = 500
_EXTRA = [
    re.compile(r"\b(?:sk|gsk|xai|pk|rk)[-_][A-Za-z0-9_\-]{12,}"),
    re.compile(r"\bGOCSPX-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)(\"?(?:api[_-]?key|token|secret|client_secret|password|authorization|access_token|refresh_token)\"?\s*[:=]\s*)\"[^\"]*\""),
    re.compile(r"[A-Za-z0-9_\-]{32,}"),  # qualquer sequencia longa e sem espaco (chave, hash, token) some
]


def clean_line(line: str) -> str:
    out = scrub(line)
    out = _EXTRA[3].sub(r'\1"***"', out)
    for rx in (_EXTRA[0], _EXTRA[1], _EXTRA[2]):
        out = rx.sub("***", out)
    return _EXTRA[4].sub("***", out)


def _tail(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-MAX_LINES:]
    except OSError:
        return "(ainda não há registro)\n"
    return "\n".join(clean_line(l) for l in lines) + "\n"


def _state() -> dict:
    """Quais conexoes existem: so sim/nao e nomes de cerebros, nunca valores."""
    out: dict = {}
    try:
        from src.jefrey.core import alexa, brains, google_oauth

        out["google_configurado"] = google_oauth.credentials() is not None
        out["cerebros"] = [b["id"] for b in brains.state()["brains"]]
        out["alexa_configurada"] = bool(alexa.status().get("configured"))
    except Exception as e:
        logger.debug("relatorio: estado parcial (%s)", type(e).__name__)
    return out


def build_report(logs_dir: Path, config_dir: Path) -> bytes:
    from src.jefrey import __version__

    info = (f"Versão do Jefrey: {__version__}\nSistema: {platform.platform()}\nPython: {platform.python_version()}\n"
            f"Gerado em: {datetime.now():%Y-%m-%d %H:%M}\n")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("info.txt", info)
        z.writestr("jefrey.log", _tail(Path(logs_dir) / "jefrey.log"))
        z.writestr("estado.json", json.dumps(_state(), ensure_ascii=False, indent=2))
    return buf.getvalue()


def reports_dir() -> Path:
    docs = Path.home() / "Documents"
    return (docs if docs.is_dir() else Path.home()) / "Jefrey" / "relatorios"


def home_logs_dir() -> Path:
    cfg = Path(os.getenv("JEFREY_CONFIG_DIR", "config"))
    return cfg.parent / "logs"
