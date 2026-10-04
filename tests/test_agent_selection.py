"""Selecao de ferramentas, roteador de intencao e recuperacao de chamadas em texto (catalogo REAL)."""
import pytest

from src.jefrey.core import tool_catalog
from src.jefrey.core.agent_loop import parse_text_tool_call, route_intent, select_tools


# ---------------- selecao ----------------
ALL = list(tool_catalog.CATALOG.keys())


@pytest.mark.parametrize("msg", ["oi, tudo bem?", "Qual a capital da Franca?", "Explique em uma frase o que e RAM",
                                 "Quem escreveu Dom Casmurro?", "me conte uma piada", "Explique em uma frase o que e memoria RAM",
                                 "o que e um metadado?"])
def test_conversa_e_conhecimento_geral_nao_oferecem_ferramentas(msg):
    assert select_tools(msg, ALL) == []


@pytest.mark.parametrize("msg,tool", [
    ("Salve uma nota chamada Mercado com: leite", "save_note"), ("Anote ai: reuniao na sexta", "save_note"),
    ("O que eu anotei sobre o mercado?", "search_notes"), ("Que horas sao agora?", "current_time"),
    ("Quanto e 15% de 240?", "calculator"), ("calcule 12 vezes 8", "calculator"),
])
def test_pedidos_com_sinal_oferecem_a_ferramenta_certa(msg, tool):
    assert tool in select_tools(msg, ALL)


@pytest.mark.parametrize("msg,expected", [
    ("Vai chover amanhã em Recife?", "weather"),
    ("Qual a PREVISÃO do tempo?", "weather"),
    ("marque uma reunião amanhã", "create_event"),
    ("mostre meus e-mails", "list_messages"),
    ("pesquise sobre gatos na internet", "search"),
    ("leia o arquivo notas.txt", "files_read"),
    ("apague a nota do mercado", "delete_note"),
])
def test_grupos_por_palavra_chave_sem_acento_nem_caixa(msg, expected):
    assert expected in select_tools(msg, ALL)


def test_so_oferece_o_que_esta_disponivel_e_no_catalogo():
    out = select_tools("vai chover?", ["current_time", "weather", "ferramenta_fantasma"])
    assert out == ["weather"]
    assert len(select_tools("pesquise e-mail agenda clima arquivo nota", ALL)) == len(set(select_tools("pesquise e-mail agenda clima arquivo nota", ALL)))


# ---------------- roteador ----------------
@pytest.mark.parametrize("msg", ["Que horas são?", "que dia é hoje", "Qual a data de hoje?", "me diga a hora atual", "Em que dia estamos"])
def test_roteador_hora(msg):
    assert route_intent(msg) == ("current_time", {})


@pytest.mark.parametrize("msg,expr", [
    ("Quanto é 17 vezes 23?", "17 * 23"), ("17*23", "17*23"), ("quanto é 2 + 2", "2 + 2"),
    ("calcule 10 / 4", "10 / 4"), ("100 menos 37", "100 - 37"), ("quanto é 3 x 4?", "3 * 4"),
])
def test_roteador_conta(msg, expr):
    name, args = route_intent(msg)
    assert name == "calculator" and args["expression"] == expr


@pytest.mark.parametrize("msg", [
    "tenho 3 gatos", "o ano de 2024 foi bom", "2024", "me ligue no 555 1234", "oi", "explique o que é RAM",
    "quanto custa um carro?", "a" * 300, "que horas devo dormir para acordar às 6?",
])
def test_roteador_nao_dispara_em_conversa_comum(msg):
    assert route_intent(msg) is None


# ---------------- recuperacao de texto ----------------
ALLOWED = {"save_note", "calculator"}


@pytest.mark.parametrize("text", [
    '{"name": "save_note", "arguments": {"title": "a"}}',
    '```json\n{"name": "save_note", "arguments": {"title": "a"}}\n```',
    '<tool_call>{"name": "save_note", "arguments": {"title": "a"}}</tool_call>',
    '{"tool": "save_note", "params": {"title": "a"}}',
    '[{"name": "save_note", "arguments": {"title": "a"}}]',
    'Claro! {"name": "save_note", "arguments": {"title": "a"}}',
    '{"name": "save_note", "arguments": "{\\"title\\": \\"a\\"}"}',
])
def test_recupera_chamada_escrita_como_texto(text):
    call = parse_text_tool_call(text, ALLOWED)
    assert call and call.name == "save_note" and call.arguments == {"title": "a"}


@pytest.mark.parametrize("text", ['{"name": "rm_rf", "arguments": {}}', "ola, tudo bem?", '{"nome": 1}', "{quebrado", '"texto"', "[1,2]"])
def test_nao_recupera_o_que_nao_e_chamada_valida(text):
    assert parse_text_tool_call(text, ALLOWED) is None




# ---------------- roteador de memoria ----------------
@pytest.mark.parametrize("msg,query", [
    ("O que eu anotei sobre a reunião?", "a reunião"),
    ("o que eu guardei sobre o mercado", "o mercado"),
    ("O que você sabe sobre minha reunião com o João?", "minha reunião com o João"),
    ("busque nas minhas notas sobre viagem", "viagem"),
    ("Quais são as minhas notas sobre dieta?", "dieta"),
])
def test_roteador_busca_em_notas_e_preserva_acentos(msg, query):
    name, args = route_intent(msg)
    assert name == "search_notes" and args == {"query": query}


@pytest.mark.parametrize("msg", [
    "o que você sabe sobre", "o que é uma nota fiscal?", "anote isto: reunião",
    "o que eu devo anotar sobre o curso?",
])
def test_roteador_de_notas_nao_dispara_sem_consulta(msg):
    assert route_intent(msg) is None
