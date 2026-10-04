"""Loop do agente com modelo falso (catalogo reduzido): execucao, aprovacao, limites."""
import asyncio

import pytest
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from src.jefrey.core import tool_catalog
from src.jefrey.core.agent_loop import LoopConfig, run_agent
from src.jefrey.core.llm_tools import ToolCall
from src.jefrey.core.tool_catalog import ToolPolicy
from src.jefrey.core.tool_runtime import ToolRuntime


def run(coro):
    return asyncio.run(coro)


# ---------------- loop ----------------
class _Args(BaseModel):
    text: str = ""
    user_id: str | None = None


EXEC: list = []


async def _tool_fn(text: str = "", user_id=None):
    EXEC.append((text, user_id))
    return f"resultado:{text}"


def mk(name):
    return StructuredTool.from_function(coroutine=_tool_fn, name=name, description="Faz algo.", args_schema=_Args)


class FakeLLM:
    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls = []

    async def stream_events(self, messages, tools=None):
        self.calls.append({"messages": [dict(m) for m in messages], "tools": tools})
        for item in self.scripts.pop(0):
            yield item


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    EXEC.clear()
    table = {"save_note": ToolPolicy("low", "Salvar nota"), "calculator": ToolPolicy("low", "Calcular"),
             "current_time": ToolPolicy("low", "Ver hora"), "delete_note": ToolPolicy("high", "Apagar nota"),
             "search_notes": ToolPolicy("low", "Buscar notas")}
    monkeypatch.setattr(tool_catalog, "CATALOG", table)
    monkeypatch.setattr("src.jefrey.core.agent_loop.CATALOG", table)


def tools_map(*names):
    return {n: mk(n) for n in names}


def go(llm, user_input, tools, **kw):
    runtime = ToolRuntime(user_id="ana", thread_id="t", resolver=lambda n: tools.get(n), **kw)

    async def collect():
        return [e async for e in run_agent(llm, runtime, [{"role": "system", "content": "s"}, {"role": "user", "content": user_input}],
                                           tools, user_input)]
    return run(collect())


def kinds(events):
    return [e["type"] for e in events]


def text_of(events):
    return "".join(e["content"] for e in events if e["type"] == "token")


def test_texto_simples_sem_ferramentas():
    llm = FakeLLM([["Ol", "a!"]])
    ev = go(llm, "oi", tools_map("save_note"))
    assert kinds(ev) == ["token", "token"] and text_of(ev) == "Ola!"
    assert len(llm.calls) == 1 and llm.calls[0]["tools"] is None  # conversa comum: nenhuma ferramenta oferecida


def test_ferramentas_so_sao_oferecidas_quando_ha_sinal_na_mensagem():
    llm = FakeLLM([["Anotado."]])
    go(llm, "anote que preciso de leite", tools_map("save_note", "search_notes", "calculator"))
    offered = {t["name"] for t in llm.calls[0]["tools"]}
    assert offered == {"save_note", "search_notes"}  # a calculadora nao e relevante aqui


def test_chamada_executa_e_o_resultado_volta_ao_modelo():
    llm = FakeLLM([[ToolCall("c1", "save_note", {"text": "leite"})], ["Anotei!"]])
    ev = go(llm, "guarde leite", tools_map("save_note"))
    assert kinds(ev) == ["tool_start", "tool_end", "token"]
    assert ev[1]["ok"] and "resultado:leite" in ev[1]["summary"] and text_of(ev) == "Anotei!"
    second = llm.calls[1]["messages"]
    assert second[-2]["role"] == "assistant" and second[-2]["tool_calls"][0]["name"] == "save_note"
    assert second[-1] == {"role": "tool", "tool_call_id": "c1", "name": "save_note", "content": "resultado:leite"}
    assert EXEC == [("leite", "ana")]


def test_texto_json_e_recuperado_e_nao_vaza_para_o_usuario():
    llm = FakeLLM([['{"name": "save_note", ', '"arguments": {"text": "x"}}'], ["Pronto."]])
    ev = go(llm, "guarde x", tools_map("save_note"))
    assert "tool_start" in kinds(ev)
    assert '{"name"' not in text_of(ev) and text_of(ev) == "Pronto."


def test_texto_que_parece_json_mas_nao_e_chamada_e_mostrado():
    llm = FakeLLM([['{"cor": "azul"}']])
    ev = go(llm, "me de um json", tools_map("save_note"))
    assert text_of(ev) == '{"cor": "azul"}' and "tool_start" not in kinds(ev)


def test_modelo_pede_ferramenta_inexistente():
    llm = FakeLLM([[ToolCall("c1", "formatar_disco", {})], ["Nao posso."]])
    ev = go(llm, "oi", tools_map("save_note"))
    end = next(e for e in ev if e["type"] == "tool_end")
    assert end["ok"] is False and end["status"] == "unknown_tool" and text_of(ev) == "Nao posso."
    assert EXEC == []


def test_atalho_hora_nao_usa_o_modelo():
    llm = FakeLLM([])  # qualquer chamada ao modelo estoura (pop de lista vazia)
    ev = go(llm, "que horas sao?", tools_map("current_time"))
    assert kinds(ev) == ["tool_start", "tool_end", "token"] and llm.calls == []
    assert text_of(ev) == "resultado:" and EXEC == [("", "ana")]


def test_atalho_calculo():
    llm = FakeLLM([])
    ev = go(llm, "quanto e 17 vezes 23", tools_map("calculator"))
    assert llm.calls == [] and ev[0]["tool"] == "calculator"


def test_ferramenta_repetida_identica_e_barrada():
    same = ToolCall("c1", "save_note", {"text": "a"})
    llm = FakeLLM([[same], [ToolCall("c2", "save_note", {"text": "a"})], ["Feito."]])
    ev = go(llm, "guarde a", tools_map("save_note"))
    assert len(EXEC) == 1 and text_of(ev) == "Feito."
    assert "ja chamou" in llm.calls[2]["messages"][-1]["content"]


def test_limite_de_passos_forca_resposta_sem_ferramentas():
    loops = [[ToolCall(f"c{i}", "save_note", {"text": str(i)})] for i in range(4)]
    llm = FakeLLM(loops + [["Resumindo: fiz o que pude."]])
    ev = go(llm, "guarde muitas", tools_map("save_note"))
    assert text_of(ev).endswith("fiz o que pude.")
    assert llm.calls[-1]["tools"] is None  # ultima chamada nao oferece ferramentas


# ---------------- aprovacao ----------------
class FakeApprovals:
    decision = "approved"

    def __init__(self, *a, **k): pass
    def create(self, **kw): return "ap-1"
    async def wait_for_decision(self, approval_id, timeout=None): return FakeApprovals.decision


@pytest.mark.parametrize("decision,executa", [("approved", True), ("rejected", False), ("expired", False)])
def test_alto_risco_emite_evento_de_aprovacao(monkeypatch, decision, executa):
    from src.jefrey.core import hitl
    FakeApprovals.decision = decision
    monkeypatch.setattr(hitl, "ApprovalManager", FakeApprovals)
    llm = FakeLLM([[ToolCall("c1", "delete_note", {"text": "n1"})], ["Ok."]])
    ev = go(llm, "apague a nota n1", tools_map("delete_note"))
    ks = kinds(ev)
    assert ks.index("tool_start") < ks.index("approval_required") < ks.index("tool_end")
    appr = next(e for e in ev if e["type"] == "approval_required")
    assert appr["approval_id"] == "ap-1" and appr["label"] == "Apagar nota"
    assert next(e for e in ev if e["type"] == "tool_end")["ok"] is executa
    assert bool(EXEC) is executa


# ---------------- atalho de memoria: busca + resumo pelo modelo ----------------
class _QArgs(BaseModel):
    query: str
    user_id: str | None = None


async def _search_fn(query: str, user_id=None):
    EXEC.append((query, user_id))
    return "- reuniao na sexta"


def search_tool():
    return {"search_notes": StructuredTool.from_function(coroutine=_search_fn, name="search_notes",
                                                         description="Busca notas.", args_schema=_QArgs)}


def test_busca_em_notas_e_resumida_pelo_modelo_sem_ferramentas():
    llm = FakeLLM([["Voce anotou ", "uma reuniao na sexta."]])
    ev = go(llm, "o que eu anotei sobre a reuniao?", search_tool())
    assert kinds(ev) == ["tool_start", "tool_end", "token", "token"]
    assert text_of(ev) == "Voce anotou uma reuniao na sexta."
    assert len(llm.calls) == 1 and llm.calls[0]["tools"] is None
    msgs = llm.calls[0]["messages"]
    assert msgs[-2] == {"role": "tool", "tool_call_id": "route", "name": "search_notes", "content": "- reuniao na sexta"}
    assert "SOMENTE o resultado" in msgs[-1]["content"]
    assert EXEC == [("a reuniao", "ana")]


def test_busca_em_notas_sem_resposta_do_modelo_mostra_o_resultado():
    llm = FakeLLM([[]])
    ev = go(llm, "o que eu anotei sobre a reuniao?", search_tool())
    assert text_of(ev) == "- reuniao na sexta"
