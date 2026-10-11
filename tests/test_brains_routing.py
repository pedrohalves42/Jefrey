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


def test_cerebro_que_nao_responde_em_3_segundos_deixa_outro_correr_junto():
    # pedido paralelo: se o primeiro demora, o proximo comeca junto; quem der o primeiro token primeiro vence
    async def lento(r):
        await asyncio.sleep(1.5)
        return sse("tarde")

    rapido_chamadas = []

    async def rapido(r):
        rapido_chamadas.append(1)
        return sse("rapido")

    a = client(lento, "a")
    b = client(rapido, "b")
    inicio = time.monotonic()
    texto = run(collect(RoutedLLM([a, b], timeout_s=5, hedge_s=0.1)))
    assert texto == "rapido"
    assert time.monotonic() - inicio < 1.0
    assert rapido_chamadas == [1]


def test_sem_demora_nao_chama_o_segundo_cerebro():
    chamadas = []

    async def bom(r):
        chamadas.append("a")
        return sse("ok")

    b_chamadas = []
    a = client(bom, "a")
    b = client(lambda r: b_chamadas.append(1) or sse("reserva"), "b")
    assert run(collect(RoutedLLM([a, b], timeout_s=5, hedge_s=2))) == "ok"
    assert b_chamadas == []


def test_429_deixa_o_cerebro_de_fora_por_mais_tempo_que_45_segundos():
    # cota estourada (Gemini/OpenAI) nao volta em 45 s: sem isso, cada pergunta gasta um pedido perdido nele
    from src.jefrey.adapters.outbound import llm_provider as P

    assert P.RATE_LIMIT_COOLDOWN_S >= 120
    relogio = [1000.0]
    memoria = {}
    a = client(lambda r: httpx.Response(429), "a")
    b = client(lambda r: sse("ok"), "b")
    run(collect(RoutedLLM([a, b], clock=lambda: relogio[0], cool=memoria)))
    relogio[0] += 60  # 60 s depois, o que estourou a cota ainda esta de fora
    chamadas_a = []
    a2 = client(lambda r: chamadas_a.append(1) or httpx.Response(429), "a")
    b2 = client(lambda r: sse("ok"), "b")
    assert run(collect(RoutedLLM([a2, b2], clock=lambda: relogio[0], cool=memoria))) == "ok"
    assert chamadas_a == []


class _Medidas:
    """Medidor falso: devolve uma ordem fixa e guarda o que o roteador registrou."""

    def __init__(self, ordem_preferida=()):
        self.linhas = []
        self.ordem = list(ordem_preferida)

    def record(self, key, role, seconds, ok, reason=""):
        self.linhas.append((key, role, ok, reason))

    def ranking(self, role, keys):
        return [k for k in self.ordem if k in keys] + [k for k in keys if k not in self.ordem]


def test_ranking_aprendido_decide_quem_vai_primeiro():
    chamadas = []
    a = client(lambda r: chamadas.append("a") or sse("do a"), "a")
    b = client(lambda r: chamadas.append("b") or sse("do b"), "b")
    medidas = _Medidas([f"{b.config.provider}|{b.config.model}|{b.config.base_url}"])
    assert run(collect(RoutedLLM([a, b], metrics=medidas))) == "do b"
    assert chamadas == ["b"]


def test_roteador_registra_sucesso_e_falha_com_motivo():
    a = client(lambda r: httpx.Response(429), "a")
    b = client(lambda r: sse("ok"), "b")
    medidas = _Medidas()
    run(collect(RoutedLLM([a, b], metrics=medidas)))
    por_ok = {ok: (key, reason) for key, role, ok, reason in medidas.linhas}
    assert por_ok[False][1] == "429" and "modelo-a" in por_ok[False][0]
    assert "modelo-b" in por_ok[True][0]


def test_defeito_no_medidor_nunca_derruba_o_chat():
    class Quebrado:
        def record(self, *a, **k):
            raise RuntimeError("banco fora do ar")

        def ranking(self, *a, **k):
            raise RuntimeError("banco fora do ar")

    a = client(lambda r: sse("segue"), "a")
    b = client(lambda r: sse("reserva"), "b")
    assert run(collect(RoutedLLM([a, b], metrics=Quebrado()))) == "segue"


def test_get_llm_client_liga_o_medidor_ao_roteador(tmp_path, monkeypatch):
    from sqlalchemy import create_engine

    import src.jefrey.core.db as dbm
    from src.jefrey.adapters.outbound import llm_provider as P

    eng = create_engine(f"sqlite:///{tmp_path}/g.db")
    monkeypatch.setattr(dbm, "get_engine", lambda: eng)
    monkeypatch.setattr(P, "_METRICS", None)
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path / "cfg"))
    P.save_override("openai", "modelo-x", "https://api.exemplo.com", None, "k")
    P.save_fallbacks([{"id": "groq", "provider": "openai", "model": "modelo-y", "base_url": "https://api.groq.com/openai", "api_key": "k"}])
    llm = P.get_llm_client()
    assert isinstance(llm, P.RoutedLLM) and llm.metrics is not None
