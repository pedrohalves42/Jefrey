"""Tipos comuns a todos os canais."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class InboundMessage:
    channel: str  # "whatsapp"
    sender: str  # identificador do remetente no canal (WhatsApp: so digitos, com DDI)
    message_id: str  # id unico da mensagem no canal (para deduplicar reenvios)
    text: str  # texto; vazio quando a mensagem nao e texto
    kind: str = "text"  # text | audio | image | other


class Channel(Protocol):
    """Quem sabe ENVIAR mensagens por um canal."""

    async def send_text(self, to: str, text: str) -> None: ...


def split_message(text: str, limit: int = 3800) -> list[str]:
    """Divide em pedacos que cabem no limite do canal, preferindo quebras de linha e espacos."""
    text = text.strip()
    if not text:
        return []
    out: list[str] = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < limit * 0.5:
            cut = text.rfind(" ", 0, limit)
        if cut < 1:
            cut = limit
        out.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        out.append(text)
    return out
