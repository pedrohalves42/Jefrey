"""Tela "O que aprendi": ver, corrigir, esquecer e desligar o aprendizado automatico."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.jefrey.core.learning import FactStore

router = APIRouter(prefix="/learning", tags=["learning"])


def _user(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    return str(uid)


class EnabledBody(BaseModel):
    enabled: bool


class TextBody(BaseModel):
    text: str = Field(min_length=3, max_length=200)


class TeachBody(BaseModel):
    text: str = Field(min_length=3, max_length=200)
    kind: str = Field(default="outro", max_length=20)


@router.post("")
async def teach(body: TeachBody, request: Request):
    """A pessoa ensina algo novo ao Jefrey (editar e apagar ja existem)."""
    uid = _user(request)
    try:
        status = FactStore().teach(uid, body.text, body.kind)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"status": status}


@router.get("")
async def list_facts(request: Request):
    uid = _user(request)
    s = FactStore()
    return {"enabled": s.enabled(uid), "facts": s.active(uid, 300)}


@router.put("")
async def set_enabled(body: EnabledBody, request: Request):
    uid = _user(request)
    FactStore().set_enabled(uid, body.enabled)
    return {"enabled": body.enabled}


@router.patch("/{fact_id}")
async def correct_fact(fact_id: str, body: TextBody, request: Request):
    uid = _user(request)
    try:
        row = FactStore().correct(uid, fact_id, body.text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if row is None:
        raise HTTPException(status_code=404, detail="Não encontrei isso.")
    return row


@router.delete("/{fact_id}")
async def forget_fact(fact_id: str, request: Request):
    uid = _user(request)
    if not FactStore().forget(uid, fact_id):
        raise HTTPException(status_code=404, detail="Não encontrei isso.")
    return {"ok": True}


@router.delete("")
async def forget_everything(request: Request):
    uid = _user(request)
    from src.jefrey.core.diary import DiaryStore

    removed = FactStore().forget_all(uid)
    DiaryStore().forget_all(uid)  # os resumos dos dias tambem podem ter fatos: "esquecer tudo" apaga de verdade
    from src.jefrey.core.studies import StudyStore

    StudyStore().forget_all(uid)  # assuntos e guias nasceram do que ele sabe de voce
    from src.jefrey.core.briefing import BriefingStore

    BriefingStore().forget_all(uid)  # o resumo do dia cita o que ele estudou e aprendeu
    return {"ok": True, "removed": removed}
