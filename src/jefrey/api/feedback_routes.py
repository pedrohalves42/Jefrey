"""👍/👎 em cada resposta e medidas de desempenho por cerebro (o Jefrey aprende com o uso)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.jefrey.domain.llm_roles import ROLES

router = APIRouter(tags=["feedback"])

_cache: dict = {}


def _store():
    if "s" not in _cache:
        from src.jefrey.adapters.outbound.brain_metrics import BrainMetrics

        _cache["s"] = BrainMetrics()
    return _cache["s"]


def _user(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    return str(uid)


class FeedbackBody(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=120)
    value: str = Field(..., pattern="^(up|down)$")
    note: str = Field(default="", max_length=300)


@router.post("/feedback")
async def send_feedback(request: Request, body: FeedbackBody):
    """Guarda se a resposta ajudou (up) ou nao (down). Nao guarda o texto da conversa."""
    uid = _user(request)
    try:
        _store().add_feedback(uid, body.message_id, body.value, body.note)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"ok": True}


@router.get("/feedback/summary")
async def feedback_summary(request: Request):
    _user(request)
    return _store().feedback_counts()


@router.get("/brains/metrics")
async def brain_metrics(request: Request, role: str = "conversa"):
    """Tempo e taxa de acerto de cada cerebro nos ultimos 7 dias, para uma funcao."""
    _user(request)
    if role not in ROLES:
        raise HTTPException(status_code=422, detail="funcao desconhecida")
    return {"role": role, "brains": _store().stats(role)}
