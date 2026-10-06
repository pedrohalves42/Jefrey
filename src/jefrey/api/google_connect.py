"""Rotas do botao "Conectar Google". O retorno do Google e uma navegacao (sem login do Jefrey): protegido pelo state."""
from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import urlsplit

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
    diag = G.diagnose(str(request.base_url).rstrip("/"))
    out["redirect_uri"] = diag["redirect_uri"]  # o que o Google vai receber: precisa estar cadastrado no Cloud Console
    out["diagnosis"] = {"ok": diag["ok"], "advice": diag["advice"], "client_type": diag["client_type"]}
    return out


@router.post("/start")
async def google_start(body: StartBody, request: Request):
    uid = _user(request)
    origin = str(request.base_url).rstrip("/")
    try:
        return {"auth_url": G.begin(uid, body.services, G.redirect_uri(origin), origin)}
    except LookupError:
        raise HTTPException(status_code=409, detail="Este programa ainda não está habilitado para conectar o Google. Veja docs/GOOGLE.md.")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


def _back(entry: Optional[dict], result: str) -> RedirectResponse:
    """De volta a tela do Jefrey (a mesma origem de onde a pessoa saiu), sem expor nada na URL alem de ok/erro."""
    base = ""
    if entry:
        p = urlsplit(entry.get("return_to", ""))
        if p.scheme == "http" and p.hostname in ("127.0.0.1", "localhost", "[::1]", "::1"):
            base = entry["return_to"]
    return RedirectResponse(f"{base}/conexoes?google={result}", status_code=303)


def _google_error(r: httpx.Response) -> str:
    try:
        v = r.json().get("error", "")
        return v if isinstance(v, str) and re.fullmatch(r"[a-z_]{3,40}", v) else "desconhecido"
    except Exception:
        return "desconhecido"


async def finish(code: str, state: str, error: str) -> RedirectResponse:
    """Conclui a conexao (usado pelos dois enderecos de retorno)."""
    entry = G.consume_state(state)
    creds = G.credentials()
    if error or not code or entry is None or creds is None:
        return _back(entry, "erro")
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(G.TOKEN_URL, data={"code": code, "client_id": creds["client_id"], "client_secret": creds["client_secret"],
                                                "redirect_uri": entry["redirect"], "grant_type": "authorization_code",
                                                "code_verifier": entry["verifier"]})
            if r.status_code >= 400:
                reason = _google_error(r)
                logger.warning("google recusou a troca do codigo: %s (HTTP %s)", reason, r.status_code)  # so o MOTIVO, nunca codigo nem chave
                return _back(entry, {"invalid_client": "chave", "redirect_uri_mismatch": "retorno", "invalid_grant": "codigo"}.get(reason, "erro"))
            tok = r.json()
            if not tok.get("access_token"):
                raise ValueError("sem token")
            email: Optional[str] = None
            try:
                u = await c.get(G.USERINFO_URL, headers={"Authorization": f"Bearer {tok['access_token']}"}, timeout=10)
                if u.status_code == 200:
                    email = u.json().get("email")
            except httpx.HTTPError as _e:
                logger.debug("google: e-mail nao obtido (%s)", type(_e).__name__)
        G.save_tokens(entry["user"], entry["services"], tok, email)
    except Exception as e:  # nunca registra codigo, token nem e-mail
        logger.warning("google callback falhou: %s", type(e).__name__)
        return _back(entry, "erro")
    return _back(entry, "ok")


@router.get("/callback")
async def google_callback(code: str = "", state: str = "", error: str = ""):
    return await finish(code, state, error)


class CredsBody(BaseModel):
    client_id: str = Field(..., max_length=200)
    client_secret: str = Field(..., max_length=200)


@router.put("/credentials")
async def set_credentials(request: Request, body: CredsBody):
    """Cola as credenciais do app Google (uma vez). Nunca devolve a chave."""
    _user(request)
    try:
        G.save_credentials(body.client_id, body.client_secret)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"configured": G.credentials() is not None}


@router.delete("")
async def google_disconnect(request: Request):
    tokens = G.delete_tokens(_user(request))
    async with httpx.AsyncClient(timeout=10) as c:  # revoga no Google (melhor esforco)
        for t in tokens:
            try:
                await c.post(G.REVOKE_URL, data={"token": t})
            except httpx.HTTPError as _e:
                logger.debug("google: revogacao nao concluida (%s)", type(_e).__name__)
    return {"ok": True}
