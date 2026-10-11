"""Tarefa 1 do plano: roteamento por funcao e tempo limite antes do primeiro token."""
import asyncio
import time

import httpx

from src.jefrey.core.llm_provider import LLMClient, LLMConfig, RoutedLLM
from tests.test_llm_router import client, collect, run, sse


def test_cerebro_lento_e_trocado_pelo_proximo_antes_do_primeiro_token():
    async def lento(r):
        await asyncio.sleep(5)
        return sse("tarde demais")

    a = client(lento, "a")
    b = client(lambda r: sse("da reserva"), "b")
    inicio = time.monotonic()
    texto = run(collect(RoutedLLM([a, b], timeout_s=0.3)))
    assert texto == "da reserva"
    assert time.monotonic() - inicio < 3


def test_ordem_por_funcao_padrao_manda_o_rapido_para_o_groq_e_a_conversa_para_o_gemini():
    from src.jefrey.domain.llm_roles import order_by_role

    roles = [{"conversa", "escrita", "estudo", "visao"}, {"ferramentas", "rapido", "resumo"}, None]  # gemini, groq, 9router
    assert order_by_role([0, 1, 2], roles, "rapido")[0] == 1
    assert order_by_role([0, 1, 2], roles, "ferramentas")[0] == 1
    assert order_by_role([0, 1, 2], roles, "conversa")[0] == 0
    assert order_by_role([0, 1, 2], roles, "visao")[0] == 0


def test_conectar_groq_ou_gemini_aplica_as_funcoes_padrao(tmp_path, monkeypatch):
    from src.jefrey.adapters.outbound import brains as B
    from src.jefrey.core import llm_provider as P

    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path / "cfg"))

    async def health(self):
        return {"ok": True}
    monkeypatch.setattr(P.LLMClient, "health", health)
    run(B.connect("groq", "gsk_" + "c" * 30))
    assert set(P.load_roles()["groq"]) == {"ferramentas", "rapido", "resumo"}
