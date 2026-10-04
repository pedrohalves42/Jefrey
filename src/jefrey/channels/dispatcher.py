"""Despachante de canais: recebe mensagens, aplica as regras de seguranca e conversa com o agente.

Regras (todas fail-closed):
  - remetente fora da lista de autorizados: ignorado em silencio (o Jefrey nao vira repetidor de spam);
  - mensagem repetida (reenvio do webhook): processada uma unica vez;
  - limite de mensagens por minuto por remetente;
  - acoes de risco pedem aprovacao no proprio canal: "SIM 7F3A" / "NAO 7F3A" (codigo curto, so vale
    para o mesmo remetente e expira);
  - as respostas de aprovacao NUNCA passam pelo modelo (nao da para "convencer" a IA a aprovar).
"""
from __future__ import annotations

import asyncio
import logging
import re
import secrets
import time
import unicodedata
from collections import OrderedDict, deque
from typing import AsyncIterator, Awaitable, Callable, Optional

from src.jefrey.channels.base import Channel, InboundMessage

logger = logging.getLogger(__name__)

RunEvents = Callable[..., AsyncIterator[dict]]
Decide = Callable[[str, str, str, str], Awaitable[bool]]  # (approval_id, decisao, decided_by, user_id)

_APPROVE = {"sim", "s", "ok", "aprovo", "aprovado", "autorizo", "pode"}
_DENY = {"nao", "n", "negar", "nego", "cancela", "cancelar"}
_REPLY = re.compile(r"^\s*([a-zA-ZÀ-ÿ]+)(?:\s+([0-9a-fA-F]{4}))?\s*[.!]?\s*$")


def _norm(word: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", word.lower()) if unicodedata.category(c) != "Mn")


def parse_approval_reply(text: str) -> Optional[tuple[str, Optional[str]]]:
    """('approved'|'rejected', codigo|None) se o texto for uma resposta de aprovacao; senao None."""
    m = _REPLY.match(text or "")
    if not m:
        return None
    word = _norm(m.group(1))
    code = m.group(2).upper() if m.group(2) else None
    if word in _APPROVE:
        return "approved", code
    if word in _DENY:
        return "rejected", code
    return None


class _Pending:
    __slots__ = ("sender", "approval_id", "user_id", "label", "expires")

    def __init__(self, sender: str, approval_id: str, user_id: str, label: str, expires: float):
        self.sender, self.approval_id, self.user_id, self.label, self.expires = sender, approval_id, user_id, label, expires


class ChannelDispatcher:
    def __init__(
        self,
        channel: Channel,
        user_for: Callable[[str], Optional[str]],
        run_events: RunEvents,
        decide: Decide,
        *,
        name: str = "whatsapp",
        rate_per_min: int = 20,
        dedupe_ttl: float = 3600.0,
        approval_ttl: float = 1800.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.channel, self.user_for, self.run_events, self.decide = channel, user_for, run_events, decide
        self.name, self.rate, self.dedupe_ttl, self.approval_ttl, self.clock = name, rate_per_min, dedupe_ttl, approval_ttl, clock
        self._seen: "OrderedDict[str, float]" = OrderedDict()
        self._hits: dict[str, deque] = {}
        self._pending: dict[str, _Pending] = {}  # codigo -> pendencia
        self._locks: dict[str, asyncio.Lock] = {}
        self._warned_rate: dict[str, float] = {}

    # ---------------------------------------------------------------- utilidades
    def _dup(self, mid: str) -> bool:
        now = self.clock()
        while self._seen and next(iter(self._seen.values())) < now - self.dedupe_ttl:
            self._seen.popitem(last=False)
        if mid in self._seen:
            return True
        self._seen[mid] = now
        while len(self._seen) > 5000:
            self._seen.popitem(last=False)
        return False

    def _limited(self, sender: str) -> bool:
        now = self.clock()
        q = self._hits.setdefault(sender, deque())
        while q and q[0] < now - 60:
            q.popleft()
        if len(q) >= self.rate:
            return True
        q.append(now)
        return False

    def _purge(self) -> None:
        now = self.clock()
        for code in [c for c, p in self._pending.items() if p.expires < now]:
            self._pending.pop(code, None)

    def _new_code(self) -> str:
        for _ in range(20):
            code = secrets.token_hex(2).upper()
            if code not in self._pending:
                return code
        return secrets.token_hex(3).upper()

    async def _say(self, to: str, text: str) -> None:
        try:
            await self.channel.send_text(to, text)
        except Exception as e:  # falha de envio nao derruba o processamento
            logger.warning("%s: nao consegui enviar resposta (%s)", self.name, type(e).__name__)

    def pending_for(self, sender: str) -> list[str]:
        self._purge()
        return [c for c, p in self._pending.items() if p.sender == sender]

    # ---------------------------------------------------------------- entrada
    async def handle(self, msg: InboundMessage) -> None:
        user_id = self.user_for(msg.sender)
        if not user_id:
            logger.info("%s: remetente nao autorizado (...%s) ignorado", self.name, msg.sender[-4:])
            return
        if self._dup(f"{msg.channel}:{msg.message_id}"):
            return
        if msg.kind != "text":
            await self._say(msg.sender, "Por enquanto eu só entendo mensagens de texto por aqui.")
            return
        if not msg.text:
            return

        reply = parse_approval_reply(msg.text)
        if reply:
            handled = await self._handle_approval(msg, user_id, *reply)
            if handled:
                return  # nunca chega ao modelo

        if self._limited(msg.sender):
            now = self.clock()
            if self._warned_rate.get(msg.sender, -1e9) < now - 60:
                self._warned_rate[msg.sender] = now
                await self._say(msg.sender, "Muitas mensagens em pouco tempo. Espere um minuto e tente de novo.")
            return

        lock = self._locks.setdefault(msg.sender, asyncio.Lock())
        async with lock:  # uma conversa por vez por pessoa
            await self._run_agent(msg, user_id)

    # ---------------------------------------------------------------- aprovacoes
    async def _handle_approval(self, msg: InboundMessage, user_id: str, decision: str, code: Optional[str]) -> bool:
        """True se a mensagem era uma resposta de aprovacao (tratada aqui)."""
        mine = self.pending_for(msg.sender)
        if code is None:
            if len(mine) == 1:
                code = mine[0]
            elif len(mine) > 1:
                await self._say(msg.sender, "Tenho mais de um pedido esperando. Responda com o código, por exemplo: SIM " + mine[0])
                return True
            else:
                return False  # "sim"/"nao" soltos sem nada pendente: e conversa normal
        p = self._pending.get(code)
        if p is None or p.sender != msg.sender or p.expires < self.clock():
            if mine or code:
                await self._say(msg.sender, "Não encontrei esse pedido de aprovação (talvez já tenha expirado).")
            return True
        self._pending.pop(code, None)
        try:
            ok = await self.decide(p.approval_id, decision, f"{self.name}:{msg.sender}", p.user_id)
        except Exception as e:
            logger.warning("%s: decisao falhou (%s)", self.name, type(e).__name__)
            ok = False
        if not ok:
            await self._say(msg.sender, "Não consegui registrar sua decisão (o pedido pode já ter sido resolvido).")
        else:
            await self._say(msg.sender, "✅ Aprovado. Já estou fazendo." if decision == "approved" else "🚫 Negado. Não vou fazer isso.")
        return True

    async def _ask(self, sender: str, user_id: str, ev: dict) -> None:
        code = self._new_code()
        label = str(ev.get("label") or ev.get("tool") or "uma ação")
        self._pending[code] = _Pending(sender, str(ev.get("approval_id")), user_id, label, self.clock() + self.approval_ttl)
        await self._say(sender, f"⚠️ Preciso da sua aprovação para: {label}.\nResponda *SIM {code}* para autorizar ou *NÃO {code}* para negar.")

    # ---------------------------------------------------------------- agente
    async def _run_agent(self, msg: InboundMessage, user_id: str) -> None:
        thread_id = f"{msg.channel[:2]}-{msg.sender}"[:128]
        parts: list[str] = []
        error: Optional[str] = None
        try:
            async for ev in self.run_events(msg.text, user_id=user_id, thread_id=thread_id):
                t = ev.get("type")
                if t == "token":
                    parts.append(str(ev.get("content", "")))
                elif t == "approval_required":
                    await self._ask(msg.sender, user_id, ev)
                elif t == "error":
                    error = str(ev.get("message") or "")
        except Exception as e:
            logger.error("%s: agente falhou: %s", self.name, e, exc_info=True)
            error = "Algo deu errado ao responder. Tente de novo."
        text = "".join(parts).strip()
        if not text:
            text = error or "Desculpe, não consegui formular uma resposta."
        await self._say(msg.sender, text)
