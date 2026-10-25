"""Modelo que some (erro 404) e trocado sozinho por um alternativo que funcione."""
import asyncio

import httpx
import pytest

from src.jefrey.adapters.outbound import brains as B
from src.jefrey.core import llm_provider as P

CHAVE = "AIza" + "x" * 35


@pytest.fixture(autouse=True)
def pasta(tmp_path, monkeypatch):
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.delenv("JEFREY_LLM__API_KEY", raising=False)


def _erro(code):
    req = httpx.Request("POST", "https://exemplo.test")
    return httpx.HTTPStatusError("erro", request=req, response=httpx.Response(code, request=req, text="model not found"))


def _conecta(monkeypatch, modelo):
    async def health(self):
        return {"ok": True}
    monkeypatch.setattr(P.LLMClient, "health", health)
    B._BY_ID["gemini"]["model"] = modelo
    asyncio.run(B.connect("gemini", CHAVE))


def test_modelo_que_sumiu_e_trocado_pelo_que_funciona(monkeypatch):
    original = B._BY_ID["gemini"]["model"]
    try:
        _conecta(monkeypatch, "gemini-2.5-flash")

        async def chat(self, messages, *a, **k):
            if self.config.model != "gemini-flash-latest":
                raise _erro(404)
            return "ok"
        monkeypatch.setattr(P.LLMClient, "chat", chat)
        mudou = asyncio.run(B.heal_models())
        assert mudou == ["gemini: gemini-flash-latest"]
        assert B._entries()[0]["model"] == "gemini-flash-latest"
    finally:
        B._BY_ID["gemini"]["model"] = original


def test_modelo_que_funciona_nao_e_mexido(monkeypatch):
    original = B._BY_ID["gemini"]["model"]
    try:
        _conecta(monkeypatch, "gemini-2.5-flash")

        async def chat(self, messages, *a, **k):
            return "ok"
        monkeypatch.setattr(P.LLMClient, "chat", chat)
        assert asyncio.run(B.heal_models()) == []
        assert B._entries()[0]["model"] == "gemini-2.5-flash"
    finally:
        B._BY_ID["gemini"]["model"] = original


def test_erro_que_nao_e_modelo_nao_troca_nada(monkeypatch):
    original = B._BY_ID["gemini"]["model"]
    try:
        _conecta(monkeypatch, "gemini-2.5-flash")

        async def chat(self, messages, *a, **k):
            raise _erro(429)
        monkeypatch.setattr(P.LLMClient, "chat", chat)
        assert asyncio.run(B.heal_models()) == []
        assert B._entries()[0]["model"] == "gemini-2.5-flash"
    finally:
        B._BY_ID["gemini"]["model"] = original
