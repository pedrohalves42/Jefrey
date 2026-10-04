"""Termos, politica de privacidade e os seus dados (ver, baixar, apagar)."""
from __future__ import annotations

import json
import logging

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from src.jefrey.core import google_oauth as G
from src.jefrey.core import privacy as P

logger = logging.getLogger(__name__)
router = APIRouter(tags=["privacy"])


def _user(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    return str(uid)


@router.get("/legal/documents")
async def legal_documents(request: Request):
    _user(request)
    return P.documents()


@router.get("/legal/status")
async def legal_status(request: Request):
    return {"accepted": P.ConsentStore().accepted(_user(request)), "version": P.TERMS_VERSION}


@router.post("/legal/accept")
async def legal_accept(request: Request):
    P.ConsentStore().accept(_user(request))
    return {"accepted": True, "version": P.TERMS_VERSION}


@router.get("/privacy/summary")
async def privacy_summary(request: Request):
    return P.summary(_user(request))


@router.get("/privacy/export")
async def privacy_export(request: Request):
    """Uma copia de tudo que o Jefrey guarda sobre a pessoa (arquivo JSON legivel)."""
    data = P.export_all(_user(request))
    body = json.dumps(data, ensure_ascii=False, indent=2)
    return Response(content=body, media_type="application/json; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="meus-dados-jefrey.json"', "Cache-Control": "no-store"})


class EraseBody(BaseModel):
    confirm: str


@router.post("/privacy/erase")
async def privacy_erase(body: EraseBody, request: Request):
    """Apaga os dados pessoais. Exige a palavra APAGAR (evita toque sem querer)."""
    uid = _user(request)
    if body.confirm.strip().upper() != "APAGAR":
        raise HTTPException(status_code=422, detail="Digite APAGAR para confirmar.")
    res = P.erase_all(uid)
    tokens = res.pop("_google_tokens", []) or []
    async with httpx.AsyncClient(timeout=10) as c:  # o Google e avisado para revogar (melhor esforco)
        for t in tokens:
            try:
                await c.post(G.REVOKE_URL, data={"token": t})
            except httpx.HTTPError as _e:
                logger.debug("revogacao do Google nao concluida (%s)", type(_e).__name__)
    return {"ok": True, "apagado": res}
