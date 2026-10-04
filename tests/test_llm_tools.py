"""Chamada de ferramentas nativa: conversao de mensagens e leitura de streaming (sem rede)."""
import asyncio
import json

import httpx
import pytest

from src.jefrey.core.llm_provider import LLMClient, LLMConfig
from src.jefrey.core.llm_tools import StreamParser, ToolCall, to_provider_messages, tool_defs

TOOLS = [{"name": "save_note", "description": "Salva nota",
          "parameters": {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}}]

HISTORY = [
    {"role": "system", "content": "voce e o Jefrey"},
    {"role": "user", "content": "salve uma nota"},
    {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "name": "save_note", "arguments": {"title": "oi"}}]},
    {"role": "tool", "tool_call_id": "c1", "name": "save_note", "content": "salvo"},
]


def run(coro):
    return asyncio.run(coro)


# ---------------- definicoes ----------------
def test_defs_por_provedor():
    assert tool_defs("ollama", TOOLS)[0]["function"]["name"] == "save_note"
    assert tool_defs("openai", TOOLS)[0]["type"] == "function"
    a = tool_defs("anthropic", TOOLS)[0]
    assert a["name"] == "save_note" and "input_schema" in a and "function" not in a


# ---------------- mensagens ----------------
def test_mensagens_ollama():
    _, m = to_provider_messages("ollama", HISTORY)
    assert m[2]["tool_calls"][0]["function"] == {"name": "save_note", "arguments": {"title": "oi"}}
    assert m[3] == {"role": "tool", "tool_name": "save_note", "content": "salvo"}


def test_mensagens_openai_argumentos_viram_texto_json():
    _, m = to_provider_messages("openai", HISTORY)
    call = m[2]["tool_calls"][0]
    assert call["id"] == "c1" and json.loads(call["function"]["arguments"]) == {"title": "oi"}
    assert m[3] == {"role": "tool", "tool_call_id": "c1", "content": "salvo"}


def test_mensagens_anthropic_system_separado_e_tool_result_em_user():
    system, m = to_provider_messages("anthropic", HISTORY)
    assert system == "voce e o Jefrey"
    assert [x["role"] for x in m] == ["user", "assistant", "user"]
    assert m[1]["content"] == [{"type": "tool_use", "id": "c1", "name": "save_note", "input": {"title": "oi"}}]
    assert m[2]["content"] == [{"type": "tool_result", "tool_use_id": "c1", "content": "salvo"}]


def test_anthropic_junta_resultados_consecutivos():
    msgs = HISTORY[:3] + [
        {"role": "tool", "tool_call_id": "c1", "name": "a", "content": "r1"},
        {"role": "tool", "tool_call_id": "c2", "name": "b", "content": "r2"},
    ]
    _, m = to_provider_messages("anthropic", msgs)
    assert len(m[-1]["content"]) == 2 and m[-1]["role"] == "user"


# ---------------- leitura de streaming ----------------
def collect(provider, lines):
    p = StreamParser(provider)
    out = []
    for ln in lines:
        out += p.feed(ln)
        if p.done:
            break
    out += p.flush()
    return out


def test_stream_ollama_texto_e_chamada():
    out = collect("ollama", [
        json.dumps({"message": {"content": "Vou salvar"}}),
        json.dumps({"message": {"content": "", "tool_calls": [{"function": {"name": "save_note", "arguments": {"title": "x"}}}]}}),
        json.dumps({"done": True}),
    ])
    assert out[0] == "Vou salvar"
    assert out[1] == ToolCall("call_1", "save_note", {"title": "x"})


def test_stream_openai_junta_pedacos_de_argumentos():
    def d(delta, finish=None):
        return "data: " + json.dumps({"choices": [{"delta": delta, "finish_reason": finish}]})
    out = collect("openai", [
        d({"content": "ok"}),
        d({"tool_calls": [{"index": 0, "id": "abc", "function": {"name": "save_note", "arguments": '{"ti'}}]}),
        d({"tool_calls": [{"index": 0, "function": {"arguments": 'tle": "y"}'}}]}),
        d({}, "tool_calls"),
        "data: [DONE]",
    ])
    assert out == ["ok", ToolCall("abc", "save_note", {"title": "y"})]


def test_stream_openai_duas_chamadas_em_paralelo():
    def d(delta):
        return "data: " + json.dumps({"choices": [{"delta": delta}]})
    out = collect("openai", [
        d({"tool_calls": [{"index": 0, "id": "a", "function": {"name": "x", "arguments": "{}"}},
                          {"index": 1, "id": "b", "function": {"name": "y", "arguments": "{}"}}]}),
        "data: [DONE]",
    ])
    assert [c.name for c in out] == ["x", "y"]


def test_stream_anthropic_tool_use_com_json_parcial():
    def e(o):
        return "data: " + json.dumps(o)
    out = collect("anthropic", [
        e({"type": "content_block_start", "index": 0, "content_block": {"type": "text"}}),
        e({"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "ola"}}),
        e({"type": "content_block_stop", "index": 0}),
        e({"type": "content_block_start", "index": 1, "content_block": {"type": "tool_use", "id": "tu1", "name": "save_note"}}),
        e({"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": '{"title"'}}),
        e({"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": ': "z"}'}}),
        e({"type": "content_block_stop", "index": 1}),
        e({"type": "message_stop"}),
    ])
    assert out == ["ola", ToolCall("tu1", "save_note", {"title": "z"})]


@pytest.mark.parametrize("provider", ["ollama", "openai", "anthropic"])
def test_stream_ignora_lixo(provider):
    assert collect(provider, ["", "lixo", "data: {nao json}", ": comentario"]) == []


def test_argumentos_invalidos_viram_dict_vazio():
    out = collect("ollama", [json.dumps({"message": {"tool_calls": [{"function": {"name": "x", "arguments": "texto solto"}}]}})])
    assert out[0].arguments == {}


# ---------------- cliente de ponta a ponta (transporte simulado) ----------------
def test_cliente_envia_ferramentas_e_devolve_chamada():
    seen = {}

    def h(req):
        body = json.loads(req.content)
        seen["tools"] = body.get("tools")
        seen["roles"] = [m["role"] for m in body["messages"]]
        line = json.dumps({"message": {"tool_calls": [{"function": {"name": "save_note", "arguments": {"title": "t"}}}]}})
        return httpx.Response(200, text=line + "\n" + json.dumps({"done": True}))

    c = LLMClient(LLMConfig("ollama", "m", "http://ollama:11434"), transport=httpx.MockTransport(h))

    async def go():
        return [x async for x in c.stream_events(HISTORY[:2], tools=TOOLS)]

    items = run(go())
    assert seen["tools"][0]["function"]["name"] == "save_note"
    assert seen["roles"] == ["system", "user"]
    assert items == [ToolCall("call_1", "save_note", {"title": "t"})]


def test_stream_texto_continua_funcionando_sem_ferramentas():
    c = LLMClient(LLMConfig("ollama", "m", "http://ollama:11434"),
                  transport=httpx.MockTransport(lambda r: httpx.Response(200, text='{"message":{"content":"oi"}}\n{"done":true}')))

    async def go():
        return [x async for x in c.stream([{"role": "user", "content": "x"}])]

    assert run(go()) == ["oi"]
