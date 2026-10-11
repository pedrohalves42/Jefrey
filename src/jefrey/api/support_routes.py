"""POST /support/report: gera o relatorio sem segredos em Documentos/Jefrey/relatorios e abre a pasta. Nunca envia nada."""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from src.jefrey.core import support as S

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/support", tags=["support"])


def _open_folder(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]


@router.post("/report")
async def report(request: Request):
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    data = S.build_report(S.home_logs_dir(), Path(os.getenv("JEFREY_CONFIG_DIR", "config")))
    folder = S.reports_dir()
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"jefrey-relatorio-{datetime.now():%Y%m%d-%H%M}.zip"
    out.write_bytes(data)
    try:
        _open_folder(folder)
    except OSError as _e:
        logger.debug("relatorio: nao abriu a pasta (%s)", type(_e).__name__)  # a pasta ja existe; a tela mostra o caminho
    return {"ok": True, "path": str(out)}
