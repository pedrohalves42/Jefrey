"""Resumo do dia, estado do que o Jefrey faz em segundo plano e ajustes de proatividade."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.jefrey.core import activity
from src.jefrey.core import briefing as B
from src.jefrey.core.reminders import local_tz

router = APIRouter(prefix="/briefing", tags=["briefing"])
activity_router = APIRouter(prefix="/system", tags=["system"])


def _user(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    return str(uid)


class PrefsBody(BaseModel):
    enabled: Optional[bool] = None
    hour: Optional[int] = None
    notify: Optional[bool] = None


@router.get("")
async def today(request: Request):
    uid = _user(request)
    day = datetime.now(local_tz()).date().isoformat()
    return {"briefing": B.BriefingStore().get(uid, day), "prefs": B.BriefingStore().get_prefs(uid)}


@router.post("/now")
async def make_now(request: Request):
    """Gera (de novo) o resumo de hoje, a pedido."""
    uid = _user(request)
    now = datetime.now(local_tz())
    B.generate(uid, now)
    return {"briefing": B.BriefingStore().get(uid, now.date().isoformat())}


@router.post("/seen")
async def seen(request: Request):
    uid = _user(request)
    return {"ok": B.BriefingStore().mark_seen(uid, datetime.now(local_tz()).date().isoformat())}


@router.put("/prefs")
async def set_prefs(body: PrefsBody, request: Request):
    uid = _user(request)
    try:
        return B.BriefingStore().set_prefs(uid, enabled=body.enabled, hour=body.hour, notify=body.notify)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@activity_router.get("/telemetry")
async def telemetry(request: Request):
    """Medidores do painel: memoria, processador, tempo ligado e qual cerebro esta pensando."""
    _user(request)
    from src.jefrey.core import brains, sysinfo

    snap = sysinfo.snapshot()
    names = {c["id"]: c["name"] for c in brains.public_catalog()}
    st = brains.state()["brains"]
    snap["brain"] = names.get(st[0]["id"], st[0]["id"]) if st else None
    snap["reserves"] = max(0, len(st) - 1)
    return snap


@activity_router.get("/activity")
async def what_is_jefrey_doing(request: Request):
    """O que o Jefrey faz sozinho agora (a tela mostra no avatar)."""
    return activity.current(_user(request))
