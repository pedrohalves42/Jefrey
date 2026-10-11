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


def test_cerebro_lento_fica_de_fora_nos_pedidos_seguintes():
    # cada pedido cria um RoutedLLM novo: a memoria de quem esta lento precisa sobreviver entre eles
    chamadas = []

    async def lento(r):
        chamadas.append("a")
        await asyncio.sleep(5)
        return sse("tarde demais")

    memoria = {}
    a = client(lento, "a")
    b = client(lambda r: sse("da reserva"), "b")
    run(collect(RoutedLLM([a, b], timeout_s=0.3, cool=memoria)))
    inicio = time.monotonic()
    texto = run(collect(RoutedLLM([client(lento, "a"), client(lambda r: sse("da reserva"), "b")], timeout_s=0.3, cool=memoria)))
    assert texto == "da reserva"
    assert len(chamadas) == 1  # o lento nao foi procurado de novo
    assert time.monotonic() - inicio < 1


def test_9router_ganha_mais_tempo_que_os_outros():
    async def atrasado(r):
        await asyncio.sleep(0.25)
        return sse("do 9router")

    async def mais_atrasado(r):
        await asyncio.sleep(1.0)
        return sse("da nuvem")

    router = LLMClient(LLMConfig("openai", "gamehouse", "http://127.0.0.1:20128/v1", api_key="k"), transport=httpx.MockTransport(atrasado))
    nuvem = LLMClient(LLMConfig("openai", "outro", "https://api.exemplo.com", api_key="k"), transport=httpx.MockTransport(mais_atrasado))
    texto = run(collect(RoutedLLM([router, nuvem], timeout_s=0.2, slow_timeout_s=0.5)))
    assert texto == "do 9router"  # 0,25 s passa no prazo do 9router (0,5 s), mas nao no da nuvem (0,2 s)
