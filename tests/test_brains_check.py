import asyncio

import httpx
import pytest

from src.jefrey.core import brains as B


def resp(code, text=""):
    return httpx.HTTPStatusError("x", request=httpx.Request("POST", "https://x"), response=httpx.Response(code, text=text, request=httpx.Request("POST", "https://x")))


@pytest.mark.parametrize("exc,trecho", [
    (resp(402, "Insufficient Balance"), "sem saldo"),
    (resp(429, '{"error":{"message":"You have no credits remaining"}}'), "sem saldo"),
    (resp(429, "slow down"), "limite"),
    (resp(401), "recusou a chave"),
    (resp(404, "The model `x` does not exist"), "modelo"),
    (resp(500), "erro 500"),
    (httpx.ConnectError("sem rede"), "chegar ao serviço"),
    (RuntimeError("???"), "não respondeu"),
])
def test_motivo_em_portugues_simples(exc, trecho):
    msg = B.explain_failure(exc)
    assert trecho in msg and "http" not in msg.lower() and "Bearer" not in msg


def test_check_all_testa_todos_ao_mesmo_tempo_e_explica_quem_falhou(monkeypatch):
    from src.jefrey.core import llm_provider as P

    monkeypatch.setattr(P, "load_override", lambda: {"provider": "openai", "fallbacks": [{"id": "groq", "provider": "openai", "model": "m1"}, {"id": "deepseek", "provider": "openai", "model": "m2"}]})
    monkeypatch.setattr(P, "config_from_settings", lambda: P.LLMConfig("openai", "principal-model", "https://api.openai.com", api_key="k"))
    monkeypatch.setattr(P, "load_fallback_configs", lambda: [P.LLMConfig("openai", "m1", "https://api.groq.com/openai", api_key="k"), P.LLMConfig("openai", "m2", "https://api.deepseek.com", api_key="k")])

    class FakeClient:
        def __init__(self, cfg):
            self.cfg = cfg

        async def chat(self, messages):
            if self.cfg.model == "m2":
                raise resp(402, "Insufficient Balance")
            return "ok"

    monkeypatch.setattr(P, "LLMClient", FakeClient)
    out = asyncio.run(B.check_all(timeout=5))
    assert [(r["role"], r["model"], r["ok"]) for r in out] == [("principal", "principal-model", True), ("reserva", "m1", True), ("reserva", "m2", False)]
    assert "sem saldo" in out[2]["problem"] and out[0]["problem"] == ""


def test_9router_e_gemini_no_catalogo_com_enderecos_certos():
    from src.jefrey.adapters.outbound import brains as B
    from src.jefrey.adapters.outbound import llm_provider as P

    ids = [b["id"] for b in B.CATALOG]
    assert ids[:2] == ["9router", "gemini"] and not next(b for b in B.CATALOG if b["id"] == "openrouter").get("recommended")
    assert B.identify("openai", "http://127.0.0.1:20128") == "9router"
    assert B.identify("openai", "https://generativelanguage.googleapis.com/v1beta/openai") == "gemini"
    # o 9router e um roteador local para a nuvem: conta como nuvem (cerebro completo); o Ollama local nao
    assert P.LLMConfig("openai", "gamehouse", "http://127.0.0.1:20128", api_key="x").is_cloud is True
    assert P.LLMConfig("ollama", "qwen3:1.7b", "http://127.0.0.1:11434").is_cloud is False
    # o Gemini usa o caminho /chat/completions sem /v1
    assert P._chat_url("https://generativelanguage.googleapis.com/v1beta/openai") == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    assert P._chat_url("https://api.openai.com") == "https://api.openai.com/v1/chat/completions"
    assert B.key_problem("gemini", "AIza" + "x" * 30) is None
    assert "AIza" in (B.key_problem("gemini", "sk-" + "x" * 30) or "")
