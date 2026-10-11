"""Caso de uso: o Jefrey manda uma mensagem de WhatsApp quando a PESSOA pede ("manda pro Arnaldo que chego as 8").

A aprovacao (mostrando o texto) acontece ANTES, no cartao de aprovacao; aqui so se acha a conversa e se poe na fila da extensao.
"""
from __future__ import annotations

from src.jefrey.domain.whatsapp import find_chat
from src.jefrey.ports import WhatsAppStorePort


def _known_or_visible(store: WhatsAppStorePort, user_id: str, contact: str):
    """A conversa certa: as que o Jefrey ja conhece e, se nao achar, as que aparecem na lista do WhatsApp (conversas individuais).
    Uma conversa so da lista passa a ser conhecida na hora (modo "perguntar antes", como toda conversa nova que a pessoa libera)."""
    chat, hits = find_chat(store.list_chats(user_id), contact)
    if chat is not None or hits:
        return chat, hits
    visible = [{"display": i["title"], "id": i["title"], "mode": "pending"} for i in store.inbox_items(user_id)]
    pick, near = find_chat(visible, contact)
    if pick is None:
        return None, near
    known = store.touch_chat(user_id, pick["display"])
    return known, [known]


def queue_for_contact(store: WhatsAppStorePort, user_id: str, contact: str, text: str) -> str:
    chat, hits = _known_or_visible(store, user_id, contact)
    if chat is None and not hits:
        return (f"Não achei “{' '.join((contact or '').split())[:40]}” nas suas conversas do WhatsApp. "
                "Abra o WhatsApp no Jefrey (ou o WhatsApp Web) e confira o nome de quem deve receber.")
    if chat is None:
        nomes = ", ".join(c["display"] for c in hits[:4])
        return f"Achei mais de uma conversa parecida: {nomes}. Diga o nome completo de quem deve receber."
    try:
        d = store.queue_message(user_id, chat["id"], text)
    except ValueError as e:
        return str(e)
    except LookupError:
        return "Não achei essa conversa agora."
    return f"Na fila para {d['chat']}: “{d['reply']}”. O envio sai em instantes, pela janela do WhatsApp do Jefrey (ou do WhatsApp Web)."
