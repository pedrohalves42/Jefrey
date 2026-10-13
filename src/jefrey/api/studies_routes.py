"""Tela "Estudos": assuntos que o Jefrey estuda sozinho, guias com fontes, limite de gasto e horario de silencio."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.jefrey.core import studies as S

router = APIRouter(prefix="/studies", tags=["studies"])
_running: set[str] = set()


def _user(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    return str(uid)


class NewTopic(BaseModel):
    title: str = Field(min_length=3, max_length=80)


class StatusBody(BaseModel):
    status: str


class PrefsBody(BaseModel):
    enabled: Optional[bool] = None
    budget_usd: Optional[float] = None
    quiet_start: Optional[int] = None
    quiet_end: Optional[int] = None


def _cloud_ready() -> bool:
    try:
        from src.jefrey.core.llm_provider import get_llm_client

        return S._is_cloud(get_llm_client())
    except Exception:
        return False


@router.get("")
async def overview(request: Request):
    uid = _user(request)
    store = S.StudyStore()
    from datetime import datetime

    from src.jefrey.core.reminders import local_tz

    day = datetime.now(local_tz()).date().isoformat()
    return {"topics": store.list_topics(uid), "prefs": store.get_prefs(uid), "spent_today": round(store.spent_today(uid, day), 4),
            "cloud_ready": _cloud_ready()}


@router.post("")
async def add_topic(body: NewTopic, request: Request):
    uid = _user(request)
    try:
        return S.StudyStore().add_topic(uid, body.title, "manual")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/suggest")
async def suggest(request: Request):
    """Inclui os assuntos que a memoria e a curiosidade indicam."""
    uid = _user(request)
    return {"added": S.auto_topics(uid)}


@router.put("/prefs")
async def set_prefs(body: PrefsBody, request: Request):
    uid = _user(request)
    try:
        return S.StudyStore().set_prefs(uid, enabled=body.enabled, budget_usd=body.budget_usd, quiet_start=body.quiet_start, quiet_end=body.quiet_end)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.patch("/{topic_id}")
async def set_status(topic_id: str, body: StatusBody, request: Request):
    uid = _user(request)
    try:
        t = S.StudyStore().set_status(uid, topic_id, body.status)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if t is None:
        raise HTTPException(status_code=404, detail="Não encontrei esse assunto.")
    return t


@router.delete("/{topic_id}")
async def delete_topic(topic_id: str, request: Request):
    uid = _user(request)
    if not S.StudyStore().delete_topic(uid, topic_id):
        raise HTTPException(status_code=404, detail="Não encontrei esse assunto.")
    return {"ok": True}


@router.get("/{topic_id}/guide")
async def guide(topic_id: str, request: Request):
    uid = _user(request)
    g = S.StudyStore().latest_guide(uid, topic_id)
    if g is None:
        raise HTTPException(status_code=404, detail="Ainda não estudei esse assunto.")
    return g


@router.post("/{topic_id}/run")
async def run_now(topic_id: str, request: Request):
    """Estuda agora (pode levar um minuto). Uma vez por vez, por pessoa."""
    uid = _user(request)
    if uid in _running:
        raise HTTPException(status_code=409, detail="Já estou estudando. Espere terminar.")
    from datetime import datetime

    from src.jefrey.core.llm_provider import get_llm_client
    from src.jefrey.core.reminders import local_tz

    _running.add(uid)
    try:
        g = await S.study_topic(uid, topic_id, get_llm_client(), tz=local_tz())
    except S.StudyError as e:
        raise HTTPException(status_code=409, detail=str(e))
    finally:
        _running.discard(uid)
    return g


# ---------------- aprender por pedido (sem chat) e fontes indicadas pela pessoa ----------------
class LearnBody(BaseModel):
    topic: str = Field(default="", max_length=80)
    url: str = Field(default="", max_length=600)
    text: str = Field(default="", max_length=6000)
    run: bool = False  # estudar agora (leva cerca de um minuto)


class SourceBody(BaseModel):
    url: str = Field(min_length=4, max_length=600)
    title: str = Field(default="", max_length=160)


@router.post("/learn")
async def learn(body: LearnBody, request: Request):
    """"Aprenda isto": um assunto, um link ou um texto. O pedido fica guardado mesmo se estudar agora nao for possivel."""
    uid = _user(request)
    try:
        out = await S.learn_request(uid, topic=body.topic, url=body.url, text=body.text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    topic = out.get("topic")
    if body.run and topic:
        if uid in _running:
            out["run_error"] = "Já estou estudando. Espere terminar."
        else:
            from src.jefrey.core.llm_provider import get_llm_client
            from src.jefrey.core.reminders import local_tz

            _running.add(uid)
            try:
                out["guide"] = await S.study_topic(uid, topic["id"], get_llm_client(), tz=local_tz())
            except S.StudyError as e:
                out["run_error"] = str(e)
            finally:
                _running.discard(uid)
    return out


@router.get("/sources")
async def list_sources(request: Request):
    return {"sources": S.StudyStore().list_sources(_user(request))}


@router.post("/{topic_id}/sources")
async def add_source(topic_id: str, body: SourceBody, request: Request):
    uid = _user(request)
    try:
        return S.StudyStore().add_source(uid, body.url, None if topic_id == "any" else topic_id, body.title)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str, request: Request):
    if not S.StudyStore().delete_source(_user(request), source_id):
        raise HTTPException(status_code=404, detail="Não encontrei essa fonte.")
    return {"ok": True}
