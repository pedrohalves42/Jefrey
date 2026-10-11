"""WhatsApp: caixa de entrada, historico lido e conversa da pessoa com ela mesma (o canal para falar com o Jefrey)."""
import asyncio

import pytest

from src.jefrey.adapters.outbound.sql_whatsapp import WAStore
from src.jefrey.application import whatsapp_inbox as A
from src.jefrey.core.tool_catalog import CATALOG
from src.jefrey.domain.whatsapp import (
    asks_whatsapp_chat, asks_whatsapp_inbox, clean_history, clean_inbox_items, format_history, format_inbox, is_bot_text, is_self_chat,
)

U = "ana"


@pytest.fixture()
def store():
    s = WAStore()
    s.forget_all(U)
    yield s
    s.forget_all(U)


def test_conversa_comigo_mesmo_e_resposta_do_robo():
    assert is_self_chat("Pedro (Você)") and is_self_chat("Pedro (you)") and not is_self_chat("Pedro")
    assert is_bot_text("🤖 São 10 horas") and not is_bot_text("São 10 horas")


def test_limpa_a_lista_de_conversas():
    itens = clean_inbox_items([
        {"title": "Maria", "preview": "vamos jantar?", "unread": 2},
        {"title": "Família", "preview": "foto", "unread": 9, "group": True},
        {"title": "Pedro (Você)", "preview": "lembrete", "unread": 0},
        {"title": "José", "preview": "minha senha é abc12345", "unread": "x"},
        "lixo",
        {"title": "", "preview": "x", "unread": 1},
    ])
    assert [(i["title"], i["unread"]) for i in itens] == [("Maria", 2), ("José", 0)]
    assert itens[1]["preview"] == ""  # previa com dado sensivel nao e guardada
    assert clean_inbox_items("nao e lista") == []


def test_limpa_o_historico():
    h = clean_history([{"id": "a", "text": "oi  tudo bem", "from_me": False}, {"id": "", "text": "sem id"}, {"id": "b", "text": "senha: 123456789 abc"}, 3])
    assert h == [{"id": "a", "text": "oi tudo bem", "from_me": False}]


def test_perguntas_sobre_mensagens():
    for t in ("Tenho mensagem no WhatsApp?", "quem me escreveu?", "chegou mensagem", "mensagens novas do zap", "tenho mensagem nova"):
        assert asks_whatsapp_inbox(t), t
    for t in ("tenho uma reunião", "manda mensagem pro João"):
        assert not asks_whatsapp_inbox(t), t
    assert asks_whatsapp_chat("O que a Maria me disse?") == "Maria"
    assert asks_whatsapp_chat("o que o Seu José falou no zap") == "Seu José"
    assert asks_whatsapp_chat("lê a conversa da Ana") == "Ana"
    for t in ("o que a gente falou", "o que você disse", "o que minha mãe falou"):
        assert asks_whatsapp_chat(t) is None, t


def test_texto_da_caixa_de_entrada():
    assert "Nenhuma mensagem nova" in format_inbox([{"title": "Maria", "preview": "oi", "unread": 0}])
    assert "extensão" in format_inbox([], connected=False)
    t = format_inbox([{"title": "Maria", "preview": "vamos jantar?", "unread": 2}, {"title": "José", "preview": "", "unread": 1}])
    assert "3 mensagens novas" in t and "2 conversas" in t and "- Maria (2): vamos jantar?" in t and "- José (1)" in t
    assert "1 mensagem nova" in format_inbox([{"title": "Maria", "preview": "", "unread": 1}])
    assert "Ainda não li" in format_history("Maria", [])
    assert format_history("Maria", [{"text": "oi", "from_me": False}, {"text": "e aí", "from_me": True}]).endswith("Maria: oi\nVocê: e aí")


def test_guarda_a_lista_e_avisa_so_de_quem_ganhou_mensagem(store):
    assert A.ingest_inbox(store, U, [{"title": "Maria", "preview": "oi", "unread": 1}]) != []
    assert A.ingest_inbox(store, U, [{"title": "Maria", "preview": "oi", "unread": 1}]) == []  # igual: nada novo
    novos = A.ingest_inbox(store, U, [{"title": "Maria", "preview": "tudo bem?", "unread": 2}, {"title": "José", "preview": "", "unread": 0}])
    assert [n["title"] for n in novos] == ["Maria"]
    assert "2 mensagens novas" in A.unread_text(store, U)
    store.set_paused(U, True)
    assert A.ingest_inbox(store, U, [{"title": "Ana", "preview": "x", "unread": 5}]) == []


def test_sem_retrato_recente_diz_que_nao_ve_o_whatsapp(store):
    assert "extensão" in A.unread_text(store, U)


def test_historico_so_de_conversa_individual_e_responde_o_que_ela_disse(store):
    store.touch_chat(U, "Maria Clara")
    assert A.ingest_history(store, U, "Maria Clara", False, [{"id": "1", "text": "vamos jantar?", "from_me": False}, {"id": "2", "text": "bora!", "from_me": True}]) == 2
    assert A.ingest_history(store, U, "Maria Clara", False, [{"id": "1", "text": "vamos jantar?", "from_me": False}]) == 0  # repetida
    assert A.ingest_history(store, U, "Família", True, [{"id": "9", "text": "oi", "from_me": False}]) == 0  # grupo nunca
    assert A.ingest_history(store, U, "Pedro (Você)", False, [{"id": "9", "text": "anotação", "from_me": True}]) == 0
    out = A.history_text(store, U, "maria")
    assert "Maria Clara: vamos jantar?" in out and "Você: bora!" in out
    assert "Não conheço" in A.history_text(store, U, "zeca")
    store.touch_chat(U, "Maria Bem")
    assert "mais de um" in A.history_text(store, U, "maria")


def test_apagar_tudo_leva_junto_caixa_e_historico(store):
    A.ingest_inbox(store, U, [{"title": "Maria", "preview": "oi", "unread": 1}])
    store.touch_chat(U, "Maria")
    A.ingest_history(store, U, "Maria", False, [{"id": "1", "text": "oi", "from_me": False}])
    store.forget_all(U)
    assert store.inbox_items(U) == [] and store.history(U, "Maria") == []


def roda(coro):
    return asyncio.run(coro)


def test_pedido_na_conversa_comigo_mesmo_vira_resposta_na_fila(store):
    async def agente(uid, texto):
        return "São 10 horas.\nBom dia!"

    d = roda(A.process_command(store, U, "Pedro (Você)", "id1", "que horas são?", agente))
    assert d["status"] == "approved" and d["reply"] == "🤖 São 10 horas. · Bom dia!"
    assert store.outbox(U)[0]["chat"] == "Pedro (Você)"
    # o mesmo pedido de novo, a resposta do proprio robo, conversa de outra pessoa, pausa: nada acontece
    assert roda(A.process_command(store, U, "Pedro (Você)", "id1", "que horas são?", agente)) is None
    assert roda(A.process_command(store, U, "Pedro (Você)", "id2", "🤖 São 10 horas", agente)) is None
    assert roda(A.process_command(store, U, "Maria", "id3", "que horas são?", agente)) is None
    store.set_paused(U, True)
    assert roda(A.process_command(store, U, "Pedro (Você)", "id4", "oi", agente)) is None


def test_falha_do_agente_responde_com_calma_e_dado_sensivel_nao_sai(store):
    async def quebra(uid, texto):
        raise RuntimeError("boom")

    async def vaza(uid, texto):
        return "sua senha é abc123456"

    async def lento(uid, texto):
        raise TimeoutError

    assert "Não consegui" in roda(A.process_command(store, U, "Pedro (Você)", "a", "oi", quebra))["reply"]
    assert "dado sensível" in roda(A.process_command(store, U, "Pedro (Você)", "b", "oi", vaza))["reply"]
    assert "demorando" in roda(A.process_command(store, U, "Pedro (Você)", "c", "oi", lento))["reply"]


def test_resposta_longa_cabe_numa_linha_so():
    from src.jefrey.domain.whatsapp import BOT_PREFIX as BOT
    out = A.one_line("a\n\nb " + "x" * 900)
    assert "\n" not in out and len(BOT) + len(out) <= 600 and out.endswith("…")


def test_ferramentas_de_leitura_sao_de_baixo_risco_e_registradas():
    for n in ("wa_inbox", "wa_conversation"):
        assert CATALOG[n].risk == "low" and not CATALOG[n].needs_approval
    from src.jefrey.core.agent_loop import route_intent

    assert route_intent("tenho mensagem no WhatsApp?") == ("wa_inbox", {})
    assert route_intent("o que a Maria me disse?") == ("wa_conversation", {"contact": "Maria"})
