"""Mandar WhatsApp por pedido da pessoa: achar a conversa certa, mostrar o texto na aprovacao, nunca enviar sem aprovar."""
import asyncio

import pytest

from src.jefrey.application.whatsapp_send import queue_for_contact
from src.jefrey.core.tool_catalog import CATALOG
from src.jefrey.domain.approval import approval_detail
from src.jefrey.domain.whatsapp import find_chat


def chats(*nomes):
    return [{"id": f"c{i}", "display": n, "mode": "ask"} for i, n in enumerate(nomes)]


def test_acha_a_conversa_por_nome_sem_acento_e_recusa_ambiguidade():
    cs = chats("Arnaldo", "Maria Clara Comercial", "Maria Bemzaozinho", "José da Silva")
    assert find_chat(cs, "arnaldo")[0]["display"] == "Arnaldo"
    assert find_chat(cs, "JOSE da silva")[0]["display"] == "José da Silva"
    assert find_chat(cs, "maria clara")[0]["display"] == "Maria Clara Comercial"
    unico, candidatas = find_chat(cs, "maria")
    assert unico is None and len(candidatas) == 2
    assert find_chat(cs, "zeca") == (None, [])
    assert find_chat(cs, "   ") == (None, [])


class Loja:
    def __init__(self, cs):
        self.cs, self.fila = cs, []

    def list_chats(self, user_id):
        return self.cs

    def queue_message(self, user_id, chat_id, text):
        if "senha" in text:
            raise ValueError("Esse texto não pode ser enviado (vazio ou com dado sensível).")
        c = next(x for x in self.cs if x["id"] == chat_id)
        self.fila.append((c["display"], text))
        return {"chat": c["display"], "reply": text}


def test_poe_na_fila_e_explica_como_vai_sair():
    loja = Loja(chats("Arnaldo"))
    out = queue_for_contact(loja, "ana", "arnaldo", "Chego às 8h")
    assert loja.fila == [("Arnaldo", "Chego às 8h")] and "Na fila para Arnaldo" in out and "WhatsApp Web" in out


def test_nao_achou_ambiguo_e_texto_proibido_viram_mensagens_claras():
    loja = Loja(chats("Maria Clara", "Maria Bemzaozinho"))
    assert "Não achei" in queue_for_contact(loja, "ana", "zeca", "oi") and "WhatsApp Web" in queue_for_contact(loja, "ana", "zeca", "oi")
    assert "mais de uma" in queue_for_contact(loja, "ana", "maria", "oi")
    assert "dado sensível" in queue_for_contact(loja, "ana", "maria clara", "minha senha é 123")
    assert loja.fila == []


def test_enviar_whatsapp_exige_aprovacao_e_a_aprovacao_mostra_o_texto():
    assert CATALOG["wa_send_message"].risk == "high" and CATALOG["wa_send_message"].needs_approval
    d = approval_detail("wa_send_message", {"contact": "Arnaldo", "message": "Chego às 8h, pode ser?"})
    assert d == "Para Arnaldo: “Chego às 8h, pode ser?”"
    assert "Assunto: Oi" in approval_detail("send_message", {"to": "a@b.c", "subject": "Oi", "body": "texto"})
    assert approval_detail("list_events", {"x": 1}) == ""
    assert len(approval_detail("wa_send_message", {"contact": "x", "message": "a" * 5000})) < 400


def test_pedidos_de_mandar_mensagem_ligam_a_ferramenta():
    from src.jefrey.core.agent_loop import select_tools

    tools = ["wa_send_message", "set_reminder", "current_time"]
    assert "wa_send_message" in select_tools("manda pro Arnaldo que eu chego às 8", tools)
    assert "wa_send_message" in select_tools("envie uma mensagem no WhatsApp para a Maria", tools)
    assert "wa_send_message" not in select_tools("que horas são", tools)


def test_a_skill_nao_manda_sem_saber_quem_pediu():
    from src.jefrey.skills.whatsapp import WhatsAppSkill

    s = WhatsAppSkill(store=Loja(chats("Arnaldo")))
    assert asyncio.run(s.wa_send_message.ainvoke({"contact": "Arnaldo", "message": "oi"})) == "Preciso saber quem você é."
    out = asyncio.run(s.wa_send_message.ainvoke({"contact": "Arnaldo", "message": "oi", "user_id": "ana"}))
    assert "Na fila para Arnaldo" in out
