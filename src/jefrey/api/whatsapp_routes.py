"""Webhook do WhatsApp Cloud API. Publico por necessidade (a Meta chama sem token do Jefrey),
mas protegido por assinatura HMAC e por lista de numeros autorizados. Desligado por padrao."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from src.jefrey.channels.dispatcher import ChannelDispatcher
from src.jefrey.channels.whatsapp import (
    WhatsAppClient, WhatsAppConfig, check_challenge, parse_webhook, verify_signature,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/channels/whatsapp", tags=["channels"])

_dispatcher: Optional[ChannelDispatcher] = None
_tasks: set[asyncio.Task] = set()  # evita que o coletor de lixo cancele tarefas em andamento
MAX_BODY = 1_000_000


def config() -> WhatsAppConfig:
    return WhatsAppConfig.from_env()


def set_dispatcher(d: Optional[ChannelDispatcher]) -> None:
    """Para testes."""
    global _dispatcher
    _dispatcher = d


async def _decide(approval_id: str, decision: str, decided_by: str, user_id: str) -> bool:
    from src.jefrey.core.hitl import ApprovalManager
    return bool(await asyncio.to_thread(ApprovalManager().decide, approval_id, decision, decided_by, user_id=user_id))


def get_dispatcher(cfg: WhatsAppConfig) -> ChannelDispatcher:
    global _dispatcher
    if _dispatcher is None:
        from src.jefrey.core.agent import Agent
        _dispatcher = ChannelDispatcher(
            channel=WhatsAppClient(cfg), user_for=cfg.user_for,
            run_events=Agent().run_events, decide=_decide, name="whatsapp",
        )
    return _dispatcher


@router.get("/webhook")
async def verify(request: Request):
    cfg = config()
    if not cfg.ready:
        raise HTTPException(status_code=404, detail="canal desligado")
    challenge = check_challenge(cfg, dict(request.query_params))
    if challenge is None:
        raise HTTPException(status_code=403, detail="verificacao recusada")
    return PlainTextResponse(challenge)


@router.post("/webhook")
async def receive(request: Request):
    cfg = config()
    if not cfg.ready:
        raise HTTPException(status_code=404, detail="canal desligado")
    body = await request.body()
    if len(body) > MAX_BODY:
        raise HTTPException(status_code=413, detail="corpo grande demais")
    if not verify_signature(cfg.app_secret, body, request.headers.get("x-hub-signature-256")):
        logger.warning("whatsapp: assinatura invalida recusada")
        raise HTTPException(status_code=403, detail="assinatura invalida")
    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(status_code=400, detail="json invalido")
    dispatcher = get_dispatcher(cfg)
    for msg in parse_webhook(payload, cfg.phone_number_id):
        task = asyncio.create_task(dispatcher.handle(msg))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    return {"ok": True}  # a Meta exige resposta rapida; o processamento segue em segundo plano
