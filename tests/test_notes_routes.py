"""Atalhos de notas: guardar um fato dito na propria frase e listar o que foi anotado."""
import pytest

from src.jefrey.core.agent_loop import route_intent
from src.jefrey.core.tool_runtime import stringify


@pytest.mark.parametrize("msg,conteudo", [
    ("Meu nome e Carla e eu moro em Curitiba. Guarda isso.", "Meu nome e Carla e eu moro em Curitiba"),
    ("Meu nome é Carla. Guarda isso", "Meu nome é Carla"),
    ("Minha cor favorita e verde, anota ai", "Minha cor favorita e verde"),
    ("anota: ligar para o dentista amanha", "ligar para o dentista amanha"),
    ("Guarde: a senha do wifi e 1234abcd", "a senha do wifi e 1234abcd"),
    ("por favor, anota - reuniao na sexta com o Joao", "reuniao na sexta com o Joao"),
    ("Moro em Curitiba. Salva isso por favor", None),  # "por favor" no fim: nao e o padrao suportado
])
def test_guardar_fato_dito_na_frase(msg, conteudo):
    r = route_intent(msg)
    if conteudo is None:
        assert r is None or r[0] != "save_note"
        return
    assert r is not None and r[0] == "save_note", r
    assert r[1]["content"] == conteudo and r[1]["title"] == conteudo[:60]


@pytest.mark.parametrize("msg", [
    "guarda isso", "anota ai", "anote isso", "Anota isso ai",  # sem conteudo: nao inventa nota
    "voce pode guardar um segredo?", "o que e anotar",
])
def test_pedido_sem_conteudo_nao_salva_nada(msg):
    r = route_intent(msg)
    assert r is None or r[0] != "save_note"


def test_titulo_limitado_a_60_caracteres():
    long = "a" * 300
    r = route_intent(f"{long}. Guarda isso")
    assert r[0] == "save_note" and len(r[1]["title"]) == 60 and r[1]["content"] == long


@pytest.mark.parametrize("msg", ["O que eu anotei?", "o que eu guardei", "minhas notas", "Mostre minhas anotações", "quais são minhas notas?"])
def test_listar_notas(msg):
    assert route_intent(msg) == ("list_notes", {})


def test_o_que_eu_anotei_sobre_x_continua_sendo_busca():
    assert route_intent("o que eu anotei sobre o dentista")[0] == "search_notes"


def test_resposta_de_salvar_nao_mostra_json_nem_id():
    out = stringify({"id": "48e4f025-4785-43fd", "title": "t", "saved": True, "message": "Anotado! Guardei na sua memória: “t”."})
    assert out.startswith("Anotado!") and "48e4" not in out


def test_lista_de_notas_nao_repete_o_titulo():
    notes = [{"content": "Cor favorita\nverde-esmeralda", "metadata": {"title": "Cor favorita"}},
             {"content": "so um texto", "metadata": {}}]
    assert stringify(notes) == "- Cor favorita: verde-esmeralda\n- so um texto"
