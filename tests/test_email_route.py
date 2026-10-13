import json

import pytest

from src.jefrey.core import agent_loop as AL
from src.jefrey.domain.email_ask import asks_unread_email, format_unread


@pytest.mark.parametrize("msg", [
    "Tenho e-mail novo?", "tenho email novo", "Quantos e-mails não lidos eu tenho?", "quantos emails novos",
    "meus e-mails não lidos", "Veja meus e-mails novos", "chegou algum e-mail?", "Tenho algum e-mail",
])
def test_perguntas_de_email_novo_sao_reconhecidas(msg):
    assert asks_unread_email(msg)


@pytest.mark.parametrize("msg", [
    "Escreva um e-mail para o João pedindo desculpas", "responda o último e-mail do Pedro", "tenho e-mail da Maria sobre a reunião de amanhã que preciso responder",
    "o que é um e-mail", "",
])
def test_outros_pedidos_continuam_com_o_modelo(msg):
    assert not asks_unread_email(msg)


def test_formatacao_com_total_e_remetentes_limpos():
    itens = [{"id": "1", "subject": "Fatura de outubro", "from": "Banco Exemplo <avisos@banco.com>"},
             {"id": "2", "subject": "Reunião amanhã", "from": '"Maria Clara" <maria@x.com>'},
             {"total_estimado": 201, "mostrando": 2}]
    out = format_unread(json.dumps(itens))
    assert out.startswith("Você tem cerca de 201 e-mails não lidos.") and "- Banco Exemplo: Fatura de outubro" in out and "- Maria Clara: Reunião amanhã" in out
    assert "banco.com" not in out
    um = format_unread(json.dumps([{"id": "1", "subject": "Oi", "from": "a@b.c"}]))
    assert um.startswith("Você tem 1 e-mail não lido.")
    assert "Tudo em dia" in format_unread("[]")
    assert "Conexões → Google" in format_unread(json.dumps([{"error": "invalid_client"}]))
    assert "Não consegui" in format_unread("não é json")


def test_roteador_usa_a_busca_de_nao_lidos():
    assert AL.route_intent("Tenho e-mail novo?") == ("search_messages", {"query": "is:unread in:inbox", "max_results": 5})
    assert AL.route_intent("Escreva um e-mail pro João") is None
