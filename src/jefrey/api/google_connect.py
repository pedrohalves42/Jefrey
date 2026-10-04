"""Rotas do botao "Conectar Google". O retorno do Google e uma navegacao (sem login do Jefrey): protegido pelo state."""
from __future__ import annotations

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from src.jefrey.core import google_oauth as G

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/connections/google", tags=["connections"])


def _user(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    return str(uid)


class StartBody(BaseModel):
    services: list[str] = Field(default_factory=lambda: ["calendar", "email"], min_length=1, max_length=3)


@router.get("")
async def google_status(request: Request):
    out = G.status(_user(request))
    out["available_services"] = [{"id": k, "label": v["label"]} for k, v in G.SERVICES.items()]
    return out


@router.post("/start")
async def google_start(body: StartBody, request: Request):
    uid = _user(request)
    redirect = str(request.base_url).rstrip("/") + "/connections/google/callback"
    try:
        return {"auth_url": G.begin(uid, body.services, redirect)}
    except LookupError:
        raise HTTPException(status_code=409, detail="Este programa ainda não está habilitado para conectar o Google. Veja docs/GOOGLE.md.")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/callback")
async def google_callback(code: str = "", state: str = "", error: str = ""):
    entry = G.consume_state(state)
    if error or not code or entry is None:
        return RedirectResponse("/conexoes?google=erro", status_code=303)
    creds = G.credentials()
    if creds is None:
        return RedirectResponse("/conexoes?google=erro", status_code=303)
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(G.TOKEN_URL, data={"code": code, "client_id": creds["client_id"], "client_secret": creds["client_secret"],
                                                "redirect_uri": entry["redirect"], "grant_type": "authorization_code",
                                                "code_verifier": entry["verifier"]})
            r.raise_for_status()
            tok = r.json()
            if not tok.get("access_token"):
                raise ValueError("sem token")
            email: Optional[str] = None
            try:
                u = await c.get(G.USERINFO_URL, headers={"Authorization": f"Bearer {tok['access_token']}"}, timeout=10)
                if u.status_code == 200:
                    email = u.json().get("email")
            except httpx.HTTPError:
                pass
        G.save_tokens(entry["user"], entry["services"], tok, email)
    except Exception as e:  # nunca registra codigo, token nem e-mail
        logger.warning("google callback falhou: %s", type(e).__name__)
        return RedirectResponse("/conexoes?google=erro", status_code=303)
    return RedirectResponse("/conexoes?google=ok", status_code=303)


@router.delete("")
async def google_disconnect(request: Request):
    tokens = G.delete_tokens(_user(request))
    async with httpx.AsyncClient(timeout=10) as c:  # revoga no Google (melhor esforco)
        for t in tokens:
            try:
                await c.post(G.REVOKE_URL, data={"token": t})
            except httpx.HTTPError:
                pass
    return {"ok": True}
