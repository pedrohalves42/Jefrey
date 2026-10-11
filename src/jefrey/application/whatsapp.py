"""Casos de uso do WhatsApp: rascunhar resposta, escrever mensagem a pedido e tratar o que chegou. So portas, nenhum banco aqui."""
from __future__ import annotations

from src.jefrey.domain.llm_roles import chat_as

import logging
from typing import Any, Optional

from src.jefrey.domain.whatsapp import (
    ASK_TOKEN, CHAT_LIMIT, HOUR_LIMIT, MAX_MSGS, MAX_TEXT, _COMPOSE_SYSTEM, _SYSTEM, chat_key, clean_reply, risk_reasons,
)
from src.jefrey.ports import PersonContextPort, WhatsAppStorePort

logger = logging.getLogger(__name__)


async def draft_reply(client: Any, name: str, known: list[str], context: list[dict], new_text: str) -> Optional[str]:
    """Pede ao modelo (SEM ferramentas) uma resposta. None = nao sabe/nao deve responder sozinho."""
    known_txt = ("\nO que voce sabe sobre " + name + " (use so se ajudar): " + "; ".join(known[:8])) if known else ""
    dialog = "\n".join(f"{'Eu' if m.get('from_me') else 'Contato'}: {str(m.get('text', ''))[:300]}" for m in context[-6:])
    messages = [{"role": "system", "content": _SYSTEM.format(name=name or "a pessoa", known=known_txt)},
                {"role": "user", "content": f"<conversa>\n{dialog}\n</conversa>\n<mensagem_nova>\n{new_text[:MAX_TEXT]}\n</mensagem_nova>"}]
    try:
        return clean_reply(await chat_as(client, messages, "escrita"))
    except Exception as e:
        logger.info("whatsapp: modelo indisponivel (%s)", type(e).__name__)
        return None


async def compose_message(client: Any, name: str, known: list[str], contact: str, instruction: str) -> Optional[str]:
    """Transforma a ideia da pessoa ('diga que chego as 8h') em uma mensagem pronta (SEM ferramentas). None = nao deu."""
    known_txt = ("\nO que voce sabe sobre " + name + " (use so se ajudar): " + "; ".join(known[:8])) if known else ""
    messages = [{"role": "system", "content": _COMPOSE_SYSTEM.format(name=name or "a pessoa", known=known_txt)},
                {"role": "user", "content": f"<contato>{contact[:80]}</contato>\n<ideia>\n{instruction[:MAX_TEXT]}\n</ideia>"}]
    try:
        return clean_reply(await chat_as(client, messages, "escrita"))
    except Exception as e:
        logger.info("whatsapp: modelo indisponivel para escrever (%s)", type(e).__name__)
        return None


# ---------------- fluxo principal ----------------
async def handle_inbound(user_id: str, payload: dict, client: Any, *, store: WhatsAppStorePort, who: PersonContextPort) -> dict:
    """Recebe o que a extensao leu e decide. Devolve {"action": "none"|"queued", ...}; nunca levanta por causa da conversa."""
    chat_name = str(payload.get("chat") or "")
    if payload.get("is_group"):
        return {"action": "none", "reason": "grupo"}
    try:
        chat = store.touch_chat(user_id, chat_name)
    except ValueError:
        return {"action": "none", "reason": "sem nome"}
    if store.paused(user_id):
        return {"action": "none", "reason": "pausado"}
    if chat["mode"] in ("pending", "off"):
        return {"action": "none", "reason": "nao liberada"}
    msgs = [m for m in (payload.get("messages") or [])[:MAX_MSGS] if isinstance(m, dict) and not m.get("from_me")]
    fresh = [m for m in msgs if store.is_new(user_id, f"{chat_key(chat_name)}|{str(m.get('id', ''))[:80]}")]
    if not fresh:
        return {"action": "none", "reason": "nada novo"}
    if store.recent_drafts(user_id, chat["id"], CHAT_LIMIT[1]) >= CHAT_LIMIT[0] or store.recent_drafts(user_id, None, 3600) >= HOUR_LIMIT:
        return {"action": "none", "reason": "limite"}
    incoming = "\n".join(str(m.get("text", ""))[:MAX_TEXT] for m in fresh).strip()
    kinds = {str(m.get("kind", "text")) for m in fresh}
    reasons = risk_reasons(incoming, "text" if kinds == {"text"} else "other")
    ids = [str(m.get("id", ""))[:80] for m in fresh]
    reply = None
    if "áudio, imagem ou outro tipo" not in reasons and incoming:
        name = who.name(user_id)
        known = who.known(user_id)
        reply = await draft_reply(client, name, known, payload.get("context") or [], incoming) if client is not None else None
    if reply is None:
        reasons.append("não sei o que responder")
        reply = ""
    needs_ask = chat["mode"] == "ask" or bool(reasons)
    if not reply:
        # sem texto sugerido: mostra para a pessoa decidir (ela pode escrever a resposta no aviso)
        needs_ask = True
    why = ", ".join(dict.fromkeys(reasons)) if reasons else ("conversa em modo perguntar antes" if chat["mode"] == "ask" else "")
    d = store.add_draft(user_id, chat, incoming, reply, why, "pending" if needs_ask else "approved", ids)
    return {"action": "queued", "draft": d["id"], "asked": needs_ask}
