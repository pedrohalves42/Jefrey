"""Caso de uso: o Jefrey manda uma mensagem de WhatsApp quando a PESSOA pede ("manda pro Arnaldo que chego as 8").

A aprovacao (mostrando o texto) acontece ANTES, no cartao de aprovacao; aqui so se acha a conversa e se poe na fila da extensao.
"""
from __future__ import annotations

from src.jefrey.domain.whatsapp import find_chat
from src.jefrey.ports import WhatsAppStorePort


def queue_for_contact(store: WhatsAppStorePort, user_id: str, contact: str, text: str) -> str:
    chat, hits = find_chat(store.list_chats(user_id), contact)
    if chat is None and not hits:
        return (f"Não achei “{' '.join((contact or '').split())[:40]}” nas suas conversas do WhatsApp. "
                "Abra essa conversa uma vez no WhatsApp Web (no Chrome) para o Jefrey conhecê-la.")
    if chat is None:
        nomes = ", ".join(c["display"] for c in hits[:4])
        return f"Achei mais de uma conversa parecida: {nomes}. Diga o nome completo de quem deve receber."
    try:
        d = store.queue_message(user_id, chat["id"], text)
    except ValueError as e:
        return str(e)
    except LookupError:
        return "Não achei essa conversa agora."
    return f"Na fila para {d['chat']}: “{d['reply']}”. O envio sai quando a conversa estiver aberta no WhatsApp Web, no Chrome."
