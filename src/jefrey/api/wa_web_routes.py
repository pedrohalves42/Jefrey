"""WhatsApp pelo navegador. Duas portas:

- /wa/...         a tela do Jefrey (login normal): parear, liberar conversas, aprovar respostas, pausar;
- /wa/device/...  a extensao do Chrome (token do aparelho): ler o que chegou, buscar o que enviar, avisar que enviou.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.jefrey.core import wa_web as W

router = APIRouter(prefix="/wa", tags=["whatsapp-web"])
MAX_BODY = 200_000
_hits: dict[str, deque] = defaultdict(deque)


def _user(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if not uid or uid in ("anonymous", "system"):
        raise HTTPException(status_code=401, detail="login necessario")
    return str(uid)


def _device_user(request: Request, limit_per_min: int = 120) -> str:
    """Autentica a extensao pelo token do aparelho (nunca na URL) e limita a frequencia."""
    auth = request.headers.get("authorization", "")
    parts = auth.split()
    token = parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else ""
    uid = W.WAStore().device_user(token)
    if uid is None:
        raise HTTPException(status_code=401, detail="aparelho nao pareado")
    q, now = _hits[token[:12]], time.monotonic()
    while q and q[0] < now - 60:
        q.popleft()
    if len(q) >= limit_per_min:
        raise HTTPException(status_code=429, detail="devagar")
    q.append(now)
    return uid


# ---------------- tela do Jefrey ----------------
class ModeBody(BaseModel):
    mode: str


class PausedBody(BaseModel):
    paused: bool


class DecideBody(BaseModel):
    decision: str
    text: Optional[str] = Field(default=None, max_length=W.MAX_REPLY)


@router.post("/pairing")
async def start_pairing(request: Request):
    return W.WAStore.begin_pairing(_user(request))


@router.get("/status")
async def status(request: Request):
    uid = _user(request)
    s = W.WAStore()
    return {"devices": s.devices(uid), "paused": s.paused(uid), "chats": s.list_chats(uid), "pending": s.list_drafts(uid, "pending"),
            "recent": [d for d in s.list_drafts(uid, None, 20) if d["status"] != "pending"]}


@router.get("/pending")
async def pending(request: Request):
    """Respostas esperando a aprovacao da pessoa (a tela pergunta de poucos em poucos segundos para abrir o aviso)."""
    uid = _user(request)
    s = W.WAStore()
    # conversas novas (ainda sem escolha): enquanto a pessoa nao disser o que fazer, o Jefrey NAO responde. A tela pergunta.
    new_chats = [c for c in s.list_chats(uid) if c["mode"] == "pending"][:20]
    return {"pending": s.list_drafts(uid, "pending", 5), "paired": bool(s.devices(uid)), "new_chats": new_chats}


@router.post("/open-extension-folder")
async def open_extension_folder(request: Request):
    """Abre a pasta da extensao do Chrome no Windows (para instalar)."""
    _user(request)
    import os
    import sys

    from src.jefrey.core.paths import public_extension_dir

    folder = public_extension_dir()
    if folder is None or sys.platform != "win32":
        raise HTTPException(status_code=404, detail="Não achei a pasta da extensão neste computador.")
    os.startfile(str(folder))  # type: ignore[attr-defined]
    return {"ok": True, "path": str(folder)}


@router.put("/paused")
async def set_paused(body: PausedBody, request: Request):
    uid = _user(request)
    W.WAStore().set_paused(uid, body.paused)
    return {"paused": body.paused}


@router.put("/chats/{chat_id}")
async def set_mode(chat_id: str, body: ModeBody, request: Request):
    uid = _user(request)
    try:
        row = W.WAStore().set_mode(uid, chat_id, body.mode)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if row is None:
        raise HTTPException(status_code=404, detail="Não encontrei essa conversa.")
    return row


class ComposeBody(BaseModel):
    instruction: str = Field(min_length=2, max_length=600)


class SendBody(BaseModel):
    text: str = Field(min_length=1, max_length=W.MAX_REPLY)


@router.post("/chats/{chat_id}/compose")
async def compose(chat_id: str, body: ComposeBody, request: Request):
    """A pessoa diz a ideia; o Jefrey escreve a mensagem para ela REVISAR (nada e enviado aqui)."""
    uid = _user(request)
    s = W.WAStore()
    chat = next((c for c in s.list_chats(uid) if c["id"] == chat_id), None)
    if chat is None:
        raise HTTPException(status_code=404, detail="conversa nao encontrada")
    client = None
    try:
        from src.jefrey.core.llm_provider import get_llm_client

        client = get_llm_client()
    except Exception:
        client = None
    from src.jefrey.core.learning import FactStore
    from src.jefrey.core.profile import ProfileStore

    name = ProfileStore().get_name(uid) or ""
    text = await W.compose_message(client, name, FactStore().profile_lines(uid, 8), chat["display"], body.instruction) if client is not None else None
    if not text:
        raise HTTPException(status_code=503, detail="Não consegui escrever agora. Você pode digitar a mensagem.")
    return {"text": text}


@router.post("/chats/{chat_id}/send")
async def send_message(chat_id: str, body: SendBody, request: Request):
    """Poe na fila a mensagem que a PESSOA aprovou; a extensao envia quando essa conversa estiver aberta no WhatsApp Web."""
    uid = _user(request)
    try:
        d = W.WAStore().queue_message(uid, chat_id, body.text)
    except LookupError:
        raise HTTPException(status_code=404, detail="conversa nao encontrada")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"ok": True, "draft": d["id"], "chat": d["chat"]}


@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str, request: Request):
    if not W.WAStore().delete_chat(_user(request), chat_id):
        raise HTTPException(status_code=404, detail="Não encontrei essa conversa.")
    return {"ok": True}


@router.post("/drafts/{draft_id}/decide")
async def decide(draft_id: str, body: DecideBody, request: Request):
    uid = _user(request)
    try:
        row = W.WAStore().decide(uid, draft_id, body.decision, body.text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if row is None:
        raise HTTPException(status_code=404, detail="Isso já foi resolvido ou não existe mais.")
    return row


@router.delete("/devices/{device_id}")
async def revoke(device_id: str, request: Request):
    if not W.WAStore().revoke_device(_user(request), device_id):
        raise HTTPException(status_code=404, detail="Não encontrei esse aparelho.")
    return {"ok": True}


@router.delete("/data")
async def forget_everything(request: Request):
    return {"ok": True, "removed": W.WAStore().forget_all(_user(request))}


# ---------------- extensao do Chrome ----------------
class PairBody(BaseModel):
    code: str = Field(min_length=6, max_length=6)
    label: str = Field(default="Chrome", max_length=60)


@router.post("/device/pair")
async def device_pair(body: PairBody, request: Request):
    ip = request.client.host if request.client else "x"
    q, now = _hits[f"pair:{ip}"], time.monotonic()
    while q and q[0] < now - 60:
        q.popleft()
    if len(q) >= 10:  # adivinhar o codigo de 6 digitos nao pode ser pratico
        raise HTTPException(status_code=429, detail="devagar")
    q.append(now)
    token = W.WAStore().complete_pairing(body.code, body.label)
    if token is None:
        raise HTTPException(status_code=403, detail="Código inválido ou vencido.")
    return {"token": token}


@router.post("/device/inbound")
async def device_inbound(request: Request):
    uid = _device_user(request, 60)
    raw = await request.body()
    if len(raw) > MAX_BODY:
        raise HTTPException(status_code=413, detail="grande demais")
    try:
        import json

        payload = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="json invalido")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="json invalido")
    client = None
    try:
        from src.jefrey.core.llm_provider import get_llm_client

        client = get_llm_client()
    except Exception:
        client = None
    return await W.handle_inbound(uid, payload, client)


@router.get("/device/poll")
async def device_poll(request: Request):
    uid = _device_user(request)
    s = W.WAStore()
    if s.paused(uid):
        return {"paused": True, "send": []}
    return {"paused": False, "send": s.outbox(uid)}


class SentBody(BaseModel):
    id: str = Field(max_length=40)
    ok: bool


@router.post("/device/sent")
async def device_sent(body: SentBody, request: Request):
    uid = _device_user(request)
    return {"ok": W.WAStore().mark_sent(uid, body.id, body.ok)}
