"""Casos de uso do WhatsApp que olham a lista de conversas: caixa de entrada, historico lido e o canal "mensagem para voce mesmo".
So portas (WhatsAppStorePort) e funcoes recebidas; nenhum banco nem modelo aqui."""
from __future__ import annotations

import logging
from typing import Awaitable, Callable, Optional

from src.jefrey.domain.learning import has_secret
from src.jefrey.domain.whatsapp import (
    BOT_PREFIX, MAX_REPLY, chat_key, clean_history, clean_inbox_items, find_chat, format_history, format_inbox, is_bot_text, is_self_chat,
)
from src.jefrey.ports import WhatsAppStorePort

logger = logging.getLogger(__name__)
AgentRunner = Callable[[str, str], Awaitable[str]]  # (user_id, texto) -> resposta
MAX_COMMAND = 1000
TIMEOUT_REPLY = "Isso está demorando mais do que o normal. Veja a resposta na janela do Jefrey."
ERROR_REPLY = "Não consegui responder agora. Tente de novo daqui a pouco."
SENSITIVE_REPLY = "Tenho a resposta, mas ela tem um dado sensível. Veja na janela do Jefrey."


def ingest_inbox(store: WhatsAppStorePort, user_id: str, raw) -> list[dict]:
    """Guarda a lista de conversas lida pela extensao. Devolve as conversas que ganharam mensagens novas."""
    if store.paused(user_id):
        return []
    return store.save_inbox(user_id, clean_inbox_items(raw))


def ingest_history(store: WhatsAppStorePort, user_id: str, chat: str, is_group: bool, raw) -> int:
    if is_group or store.paused(user_id) or is_self_chat(chat) or not chat_key(chat):
        return 0
    return store.save_history(user_id, chat, clean_history(raw))


def unread_text(store: WhatsAppStorePort, user_id: str) -> str:
    items = store.inbox_items(user_id)
    age = store.inbox_age_s(user_id)
    return format_inbox(items, connected=age is not None and age < 600)


def history_text(store: WhatsAppStorePort, user_id: str, contact: str) -> str:
    chat, candidates = find_chat(store.list_chats(user_id), contact)
    if chat is None:
        if len(candidates) > 1:
            return "Achei mais de um: " + ", ".join(c["display"] for c in candidates[:4]) + ". Qual deles?"
        return f"Não conheço nenhuma conversa com \"{contact}\" no WhatsApp."
    return format_history(chat["display"], store.history(user_id, chat["display"], 10))


def one_line(text: str, limit: int = MAX_REPLY - len(BOT_PREFIX)) -> str:
    """O campo do WhatsApp envia com Enter: a resposta vai numa linha so, no tamanho que cabe."""
    flat = " · ".join(p.strip() for p in (text or "").replace("\r", "").split("\n") if p.strip())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


async def process_command(store: WhatsAppStorePort, user_id: str, chat_title: str, cmd_id: str, text: str, run_agent: AgentRunner) -> Optional[dict]:
    """A pessoa escreveu para si mesma no WhatsApp: o Jefrey responde ali, na mesma conversa. None = ignorado."""
    text = " ".join((text or "").split())[:MAX_COMMAND]
    if not is_self_chat(chat_title) or not text or is_bot_text(text) or store.paused(user_id):
        return None
    if not store.is_new(user_id, f"cmd|{str(cmd_id)[:100]}"):
        return None
    chat = store.touch_chat(user_id, chat_title)
    try:
        reply = (await run_agent(user_id, text)).strip() or ERROR_REPLY
    except TimeoutError:
        reply = TIMEOUT_REPLY
    except Exception as e:
        logger.warning("whatsapp: comando da conversa consigo mesmo falhou (%s)", type(e).__name__)
        reply = ERROR_REPLY
    if has_secret(reply):
        reply = SENSITIVE_REPLY
    return store.add_draft(user_id, chat, text, BOT_PREFIX + one_line(reply), "resposta do Jefrey a você", "approved", [])
