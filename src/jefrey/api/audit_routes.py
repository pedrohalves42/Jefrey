"""O que o Jefrey fez hoje, em frases simples (so as acoes da propria pessoa)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request

from src.jefrey.domain.audit_report import summarize

router = APIRouter(prefix="/audit", tags=["audit"])


def _user(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    return str(uid)


def _rows(uid: str, since: datetime) -> list[dict]:
    from src.jefrey.adapters.outbound.audit import recent_for_user

    return recent_for_user(uid, since)


@router.get("/today")
async def today(request: Request):
    uid = _user(request)
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    return summarize(_rows(uid, since))
