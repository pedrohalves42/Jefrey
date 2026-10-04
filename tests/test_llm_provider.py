"""Camada de provedores de LLM: Ollama, compativel-OpenAI e Anthropic (sem rede)."""
import asyncio
import json

import httpx
import pytest

from src.jefrey.core.llm_provider import (
    LLMClient, LLMConfig, LLMConfigError, friendly_error,
)

MSGS = [{"role": "system", "content": "voce e o Jefrey"}, {"role": "user", "content": "oi"}]


def run(coro):
    return asyncio.run(coro)


def client(cfg, handler):
    return LLMClient(cfg, transport=httpx.MockTransport(handler))


def collect(c):
    async def go():
        return [x async for x in c.stream(MSGS)]
    return run(go())


# ---------------- ollama ----------------
def test_ollama_chat_and_stream():
    cfg = LLMConfig("ollama", "qwen", "http://ollama:11434")
    seen = {}

    def h(req):
        seen["url"] = str(req.url)
        body = json.loads(req.content)
        if body["stream"]:
            lines = [{"message": {"content": "Ol"}}, {"message": {"content": "a"}}, {"done": True}]
            return httpx.Response(200, text="\n".join(json.dumps(x) for x in lines))
        return httpx.Response(200, json={"message": {"content": "Ola"}})

    c = client(cfg, h)
    assert run(c.chat(MSGS)) == "Ola"
    assert seen["url"].endswith("/api/chat")
    assert "".join(collect(c)) == "Ola"


# ---------------- openai ----------------
def test_openai_chat_stream_and_auth_header():
    cfg = LLMConfig("openai", "gpt", "https://api.openai.com", api_key="sk-test")
    seen = {}

    def h(req):
        seen["auth"] = req.headers.get("authorization")
        seen["url"] = str(req.url)
        body = json.loads(req.content)
        if body["stream"]:
            sse = ['data: {"choices":[{"delta":{"content":"Ol"}}]}',
                   'data: {"choices":[{"delta":{"content":"a"}}]}', "data: [DONE]"]
            return httpx.Response(200, text="\n".join(sse))
        return httpx.Response(200, json={"choices": [{"message": {"content": "Ola"}}]})

    c = client(cfg, h)
    assert run(c.chat(MSGS)) == "Ola"
    assert seen["auth"] == "Bearer sk-test"
    assert seen["url"] == "https://api.openai.com/v1/chat/completions"
    assert "".join(collect(c)) == "Ola"


def test_openai_base_url_com_v1_nao_duplica():
    cfg = LLMConfig("openai", "m", "http://localhost:1234/v1")
    seen = {}

    def h(req):
        seen["url"] = str(req.url)
        return httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})

    run(client(cfg, h).chat(MSGS))
    assert seen["url"] == "http://localhost:1234/v1/chat/completions"


def test_openai_local_nao_exige_chave():
    LLMClient(LLMConfig("openai", "m", "http://localhost:1234"))


def test_openai_nuvem_exige_chave():
    with pytest.raises(LLMConfigError):
        LLMClient(LLMConfig("openai", "gpt", "https://api.openai.com"))


# ---------------- anthropic ----------------
def test_anthropic_system_separado_chat_e_stream():
    cfg = LLMConfig("anthropic", "claude", "https://api.anthropic.com", api_key="k")
    seen = {}

    def h(req):
        seen["key"] = req.headers.get("x-api-key")
        seen["ver"] = req.headers.get("anthropic-version")
        body = json.loads(req.content)
        seen["system"] = body.get("system")
        seen["roles"] = [m["role"] for m in body["messages"]]
        if body["stream"]:
            sse = ['data: {"type":"content_block_delta","delta":{"text":"Ol"}}',
                   'data: {"type":"content_block_delta","delta":{"text":"a"}}',
                   'data: {"type":"message_stop"}']
            return httpx.Response(200, text="\n".join(sse))
        return httpx.Response(200, json={"content": [{"type": "text", "text": "Ola"}]})

    c = client(cfg, h)
    assert run(c.chat(MSGS)) == "Ola"
    assert seen["key"] == "k" and seen["ver"]
    assert seen["system"] == "voce e o Jefrey"
    assert seen["roles"] == ["user"]
    assert "".join(collect(c)) == "Ola"


def test_anthropic_exige_chave():
    with pytest.raises(LLMConfigError):
        LLMClient(LLMConfig("anthropic", "claude", "https://api.anthropic.com"))


def test_provedor_desconhecido():
    with pytest.raises(LLMConfigError):
        LLMClient(LLMConfig("xyz", "m", "http://x"))


# ---------------- erros e diagnostico ----------------
def _status_error(code):
    req = httpx.Request("POST", "http://x")
    return httpx.HTTPStatusError("e", request=req, response=httpx.Response(code, request=req))


@pytest.mark.parametrize("code,trecho", [(401, "chave"), (404, "Modelo nao encontrado"),
                                         (429, "Limite"), (500, "memoria")])
def test_friendly_error_http(code, trecho):
    assert trecho in friendly_error(_status_error(code))


def test_friendly_error_timeout_e_conexao():
    assert "demorou" in friendly_error(httpx.ReadTimeout("t"))
    assert "conectar" in friendly_error(httpx.ConnectError("c"))


def test_health_nao_vaza_chave():
    cfg = LLMConfig("openai", "gpt", "https://api.openai.com", api_key="sk-segredo")

    def h(req):
        return httpx.Response(401)

    r = run(client(cfg, h).health())
    assert r["ok"] is False
    assert "sk-segredo" not in json.dumps(r)


def test_health_ollama_modelo_presente():
    cfg = LLMConfig("ollama", "qwen2.5:0.5b", "http://ollama:11434")
    c = client(cfg, lambda req: httpx.Response(200, json={"models": [{"name": "qwen2.5:0.5b"}]}))
    assert run(c.health())["ok"] is True
    c2 = client(cfg, lambda req: httpx.Response(200, json={"models": [{"name": "outro:1b"}]}))
    assert run(c2.health())["ok"] is False


# ---------------- metricas ----------------
def _sample(name, **labels):
    from prometheus_client import REGISTRY
    return REGISTRY.get_sample_value(name, labels)


def test_chat_e_stream_registram_latencia_e_tokens():
    cfg = LLMConfig("ollama", "modelo-metrica", "http://ollama:11434")

    def h(req):
        body = json.loads(req.content)
        if body["stream"]:
            return httpx.Response(200, text='{"message":{"content":"abcdefgh"}}\n{"done":true}')
        return httpx.Response(200, json={"message": {"content": "abcdefgh"}})

    c = client(cfg, h)
    run(c.chat(MSGS))
    collect(c)
    assert _sample("jefrey_llm_latency_seconds_count", provider="ollama", model="modelo-metrica") == 2
    assert _sample("jefrey_llm_tokens_total", type="output", provider="ollama", model="modelo-metrica") == 4  # 2 x (8//4)
    assert _sample("jefrey_llm_tokens_total", type="input", provider="ollama", model="modelo-metrica") > 0


def test_falha_de_http_nao_registra_latencia():
    cfg = LLMConfig("ollama", "modelo-falha", "http://ollama:11434")
    c = client(cfg, lambda req: httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        run(c.chat(MSGS))
    assert _sample("jefrey_llm_latency_seconds_count", provider="ollama", model="modelo-falha") is None
