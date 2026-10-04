"""Sessao 8: modelo de nuvem ve todas as ferramentas; busca na web sem chave; leitor protegido como ferramenta."""
import asyncio

import pytest
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from src.jefrey.core import persona, tool_catalog
from src.jefrey.core.agent_loop import LoopConfig, run_agent, select_tools
from src.jefrey.core.tool_catalog import ToolPolicy
from src.jefrey.core.tool_runtime import ToolRuntime


def run(coro):
    return asyncio.run(coro)


class _Args(BaseModel):
    text: str = ""
    user_id: str | None = None


async def _fn(text: str = "", user_id=None):
    return "ok"


def mk(name):
    return StructuredTool.from_function(coroutine=_fn, name=name, description="Faz algo.", args_schema=_Args)


class FakeLLM:
    def __init__(self, cloud):
        self.config = type("C", (), {"is_cloud": cloud})()
        self.calls = []

    async def stream_events(self, messages, tools=None):
        self.calls.append(tools)
        yield "ok"


@pytest.fixture(autouse=True)
def _catalogo(monkeypatch):
    table = {n: ToolPolicy("low", n) for n in ("search", "search_news", "extract", "weather", "save_note", "calculator")}
    table["delete_note"] = ToolPolicy("high", "Apagar nota")
    monkeypatch.setattr(tool_catalog, "CATALOG", table)
    monkeypatch.setattr("src.jefrey.core.agent_loop.CATALOG", table)


def _go(llm, msg, names, **kw):
    tools = {n: mk(n) for n in names}
    rt = ToolRuntime(user_id="ana", thread_id="t", resolver=lambda n: tools.get(n))

    async def coleta():
        return [e async for e in run_agent(llm, rt, [{"role": "system", "content": "s"}, {"role": "user", "content": msg}], tools, msg, **kw)]
    return run(coleta())


TODAS = ["search", "search_news", "extract", "weather", "save_note", "calculator", "delete_note"]


def test_nuvem_oferece_todas_mesmo_sem_palavra_chave():
    llm = FakeLLM(cloud=True)
    _go(llm, "o que está acontecendo no Brasil esta semana?", TODAS)
    assert {t["name"] for t in llm.calls[0]} == set(TODAS)


def test_modelo_local_continua_com_selecao_por_palavra_chave():
    llm = FakeLLM(cloud=False)
    _go(llm, "o que está acontecendo no Brasil esta semana?", TODAS)
    assert llm.calls[0] is None  # nenhuma palavra-chave: nenhuma ferramenta
    llm2 = FakeLLM(cloud=False)
    _go(llm2, "pesquise notícias sobre futebol", TODAS)
    assert {t["name"] for t in llm2.calls[0]} == {"search", "search_news", "extract"}


def test_da_para_forcar_o_modo_no_config():
    llm = FakeLLM(cloud=True)
    _go(llm, "oi", TODAS, config=LoopConfig(offer_all=False))
    assert llm.calls[0] is None
    llm2 = FakeLLM(cloud=False)
    _go(llm2, "oi", TODAS, config=LoopConfig(offer_all=True))
    assert len(llm2.calls[0]) == len(TODAS)


def test_so_oferece_o_que_esta_disponivel_e_no_catalogo():
    assert select_tools("oi", ["search", "inventada", "calculator"], offer_all=True) == ["search", "calculator"]
    assert select_tools("oi", [], offer_all=True) == []


def test_ferramenta_de_risco_continua_pedindo_aprovacao_na_nuvem():
    assert tool_catalog.CATALOG["delete_note"].needs_approval is True
    assert tool_catalog.CATALOG["search"].needs_approval is False


# ---------------- persona ----------------
def test_regra_da_web_so_entra_quando_ha_busca():
    base = dict(name="Ana", self_info="[Quem] x", memory_context="")
    com = persona.build_system_prompt(web=True, **base)
    sem = persona.build_system_prompt(web=False, **base)
    assert "WEB:" in com and "BUSQUE" in com and "data" in com and "ignore" in com
    assert "WEB:" not in sem


# ---------------- ferramentas de web ----------------
def _skill():
    from src.jefrey.skills.web_search import WebSearchSkill
    s = WebSearchSkill()
    s._client = None
    return s


def call(tool, **kw):
    """Chama a ferramenta como o runtime faz (StructuredTool.ainvoke)."""
    return run(tool.ainvoke(kw))


def test_busca_sem_chave_roda_em_outra_thread_e_nao_trava(monkeypatch):
    import threading
    visto = {}
    s = _skill()

    def falso(query, max_results=5, news=False):
        visto["thread"] = threading.current_thread() is not threading.main_thread()
        visto["news"] = news
        return {"query": query, "results": [{"title": "Dólar", "url": "https://exemplo.com/dolar", "content": "R$ 5,10", "published": "2026-10-04"}]}
    monkeypatch.setattr(s, "_fallback_ddg", falso)
    r = call(s.search, query="cotação do dólar hoje")
    assert r["results"][0]["url"].startswith("https://") and visto == {"thread": True, "news": False}
    n = call(s.search_news, query="eleições")
    assert visto["news"] is True and n["results"]


def test_erro_da_busca_nao_e_guardado_no_cache(monkeypatch):
    s = _skill()
    respostas = [{"error": "A busca na web nao respondeu agora.", "query": "q", "results": []},
                 {"query": "q", "results": [{"title": "A", "url": "https://a.com", "content": "x"}]}]
    monkeypatch.setattr(s, "_fallback_ddg", lambda q, n=5, news=False: respostas.pop(0))
    assert call(s.search, query="q")["error"]
    assert call(s.search, query="q")["results"]  # a segunda tentativa nao pegou o erro do cache


def test_extract_usa_o_leitor_protegido_sem_chave(monkeypatch):
    from src.jefrey.core import webread
    lidas = []

    async def falso(url, **kw):
        lidas.append(url)
        if "interno" in url:
            raise webread.ReadError("endereco nao permitido")
        return {"url": url, "title": "Página", "text": "texto " * 2000, "fetched_at": "2026-10-04"}
    monkeypatch.setattr(webread, "fetch_page", falso)
    r = call(_skill().extract, urls=["https://a.com/x", "http://interno/segredo", "https://b.com/y", "https://c.com/z", "https://d.com/w"])
    assert len(lidas) == 3  # no maximo 3 paginas por chamada
    assert [x["url"] for x in r["results"]] == ["https://a.com/x", "https://b.com/y"] and r["unreadable"] == ["http://interno/segredo"]
    assert all(len(x["content"]) <= 6000 for x in r["results"])
    todas_ruins = call(_skill().extract, urls=["http://interno/a"])
    assert "error" in todas_ruins and "results" not in todas_ruins
