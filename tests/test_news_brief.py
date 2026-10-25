"""Noticias direto: reconhece o pedido, monta so com o que a fonte trouxe, nao pega frases comuns."""
import pytest

from src.jefrey.application.agent_loop import route_intent
from src.jefrey.domain.news_brief import compose, news_topic


@pytest.mark.parametrize("frase,assunto", [
    ("Quais as ultimas noticias sobre inteligencia artificial?", "inteligencia artificial"),
    ("Quais as últimas notícias sobre inteligência artificial?", "inteligência artificial"),
    ("quais são as últimas notícias de futebol", "futebol"),
    ("me conta as noticias do dia", "brasil"),
    ("notícias sobre o dólar", "o dólar"),
    ("novidades da apple", "apple"),
])
def test_reconhece_pedido_de_noticias(frase, assunto):
    assert news_topic(frase) == assunto


@pytest.mark.parametrize("frase", ["bom dia", "me explica o que e noticia falsa e por que importa muito", "cria um lembrete de noticias", "que horas sao"])
def test_nao_pega_o_que_nao_e_pedido(frase):
    assert news_topic(frase) is None


def test_compose_traz_ate_tres_com_fonte():
    r = [{"title": f"Titulo {i}", "site": f"Site{i}"} for i in range(5)]
    out = compose("ia", r)
    assert out.startswith("Últimas notícias sobre ia:") and out.count("\n- ") == 3 and "(Site0)" in out


def test_compose_sem_resultado_e_titulo_gigante():
    assert compose("ia", []) == "Não achei notícias recentes sobre ia."
    assert len(compose("ia", [{"title": "x" * 500}]).split("\n")[1]) <= 115


def test_roteia_direto_sem_modelo():
    assert route_intent("Quais as ultimas noticias sobre inteligencia artificial?") == ("news_brief", {"topic": "inteligencia artificial"})


def test_ferramenta_monta_a_resposta_da_busca(monkeypatch):
    import asyncio

    from src.jefrey.skills.web_search import WebSearchSkill

    s = WebSearchSkill()

    async def fake(**kw):
        return {"results": [{"title": "IA muda o trabalho", "site": "Folha"}]}

    monkeypatch.setattr(WebSearchSkill, "search_news", property(lambda self: fake))
    out = asyncio.run(s.news_brief.ainvoke({"topic": "ia"}))
    assert "IA muda o trabalho (Folha)" in out


def test_busca_com_erro_e_dita_sem_detalhe(monkeypatch):
    import asyncio

    from src.jefrey.skills.web_search import WebSearchSkill

    async def fake(**kw):
        return {"error": "token sk-123 invalido", "results": []}

    monkeypatch.setattr(WebSearchSkill, "search_news", property(lambda self: fake))
    out = asyncio.run(WebSearchSkill().news_brief.ainvoke({"topic": "ia"}))
    assert "sk-123" not in out and "Não consegui" in out
