"""Reserva de provedores: troca antes de comecar a responder, com espera, e nunca no meio da resposta."""
import asyncio
import json

import httpx
import pytest

from src.jefrey.core import llm_provider as lp
from src.jefrey.core.llm_provider import LLMClient, LLMConfig, LLMConfigError, RoutedLLM, is_retryable


def sse(*parts):
    body = "".join("data: " + json.dumps({"choices": [{"delta": {"content": p}}]}) + "\n\n" for p in parts) + "data: [DONE]\n\n"
    return httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})


def client(handler, name="a"):
    cfg = LLMConfig("openai", f"modelo-{name}", "https://api.exemplo.com", api_key="k")
    return LLMClient(cfg, transport=httpx.MockTransport(handler))


async def collect(llm, msgs=None):
    return "".join([x async for x in llm.stream_events(msgs or [{"role": "user", "content": "oi"}]) if isinstance(x, str)])


def run(c):
    return asyncio.run(c)


def test_usa_o_principal_quando_funciona():
    calls = []
    a = client(lambda r: calls.append("a") or sse("ola"), "a")
    b = client(lambda r: calls.append("b") or sse("reserva"), "b")
    assert run(collect(RoutedLLM([a, b]))) == "ola" and calls == ["a"]


@pytest.mark.parametrize("status", [429, 500, 502, 503, 401, 403, 404])
def test_troca_para_a_reserva_em_falha_antes_de_responder(status):
    a = client(lambda r: httpx.Response(status), "a")
    b = client(lambda r: sse("da reserva"), "b")
    r = RoutedLLM([a, b])
    assert run(collect(r)) == "da reserva" and r.last_label == "openai:modelo-b"


def test_troca_quando_o_provedor_esta_fora_do_ar():
    def down(req):
        raise httpx.ConnectError("sem rede")
    assert run(collect(RoutedLLM([client(down, "a"), client(lambda r: sse("ok"), "b")]))) == "ok"


def test_troca_em_timeout():
    def slow(req):
        raise httpx.ReadTimeout("lento")
    assert run(collect(RoutedLLM([client(slow, "a"), client(lambda r: sse("ok"), "b")]))) == "ok"


def test_pedido_invalido_400_nao_aciona_reserva():
    a = client(lambda r: httpx.Response(400), "a")
    b_calls = []
    b = client(lambda r: b_calls.append(1) or sse("x"), "b")
    with pytest.raises(httpx.HTTPStatusError):
        run(collect(RoutedLLM([a, b])))
    assert b_calls == []  # outro provedor nao resolve um pedido mal formado


def test_nunca_troca_no_meio_da_resposta():
    def corta(req):
        class Boom(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b'data: {"choices":[{"delta":{"content":"meio"}}]}\n\n'
                raise httpx.ReadError("caiu")
        return httpx.Response(200, stream=Boom())
    b_calls = []
    b = client(lambda r: b_calls.append(1) or sse("x"), "b")

    async def go():
        got = []
        llm = RoutedLLM([client(corta, "a"), b])
        with pytest.raises(Exception):
            async for x in llm.stream_events([{"role": "user", "content": "oi"}]):
                got.append(x)
        return got
    got = run(go())
    assert "meio" in "".join(g for g in got if isinstance(g, str)) and b_calls == []


def test_todos_falham_levanta_o_ultimo_erro():
    a = client(lambda r: httpx.Response(429), "a")
    b = client(lambda r: httpx.Response(503), "b")
    with pytest.raises(httpx.HTTPStatusError) as ei:
        run(collect(RoutedLLM([a, b])))
    assert ei.value.response.status_code == 503


def test_provedor_que_falhou_fica_em_espera_e_depois_volta():
    t = [0.0]
    a_calls = []
    state = {"ok": False}

    def a_handler(r):
        a_calls.append(1)
        return sse("a") if state["ok"] else httpx.Response(429)
    llm = RoutedLLM([client(a_handler, "a"), client(lambda r: sse("b"), "b")], clock=lambda: t[0])
    assert run(collect(llm)) == "b" and len(a_calls) == 1
    assert run(collect(llm)) == "b" and len(a_calls) == 1  # em espera: nem tenta
    state["ok"] = True
    t[0] += lp.COOLDOWN_S + 1
    assert run(collect(llm)) == "a"  # voltou ao principal


def test_unico_provedor_em_espera_ainda_e_tentado():
    t = [0.0]
    n = []
    llm = RoutedLLM([client(lambda r: n.append(1) or httpx.Response(429), "a")], clock=lambda: t[0])
    for _ in range(2):
        with pytest.raises(httpx.HTTPStatusError):
            run(collect(llm))
    assert len(n) == 2  # sem alternativa, nao bloqueia o usuario


def test_is_retryable():
    mk = lambda c: httpx.HTTPStatusError("x", request=httpx.Request("GET", "http://x"), response=httpx.Response(c))  # noqa: E731
    assert all(is_retryable(mk(c)) for c in (401, 402, 429, 500, 503))
    assert not any(is_retryable(mk(c)) for c in (400, 422))
    assert is_retryable(httpx.ConnectError("x")) and not is_retryable(ValueError("x"))


# ---------------- configuracao ----------------
@pytest.fixture()
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path))
    lp.save_override("ollama", "qwen3:1.7b", None, None, None)
    return tmp_path


def test_sem_reservas_devolve_cliente_simples(cfg):
    assert isinstance(lp.get_llm_client(), LLMClient)


def test_salvar_e_carregar_reservas_com_chaves_no_cofre(cfg):
    lp.save_fallbacks([
        {"id": "r1", "provider": "openai", "model": "openai/gpt-6-luna", "base_url": "https://openrouter.ai/api", "api_key": "sk-or-1"},
        {"id": "r2", "provider": "anthropic", "model": "claude-sonnet-5-5", "api_key": "sk-ant-2"},
    ])
    got = lp.load_fallback_configs()
    assert [(c.provider, c.model, c.api_key) for c in got] == [
        ("openai", "openai/gpt-6-luna", "sk-or-1"), ("anthropic", "claude-sonnet-5-5", "sk-ant-2")]
    assert isinstance(lp.get_llm_client(), RoutedLLM)
    assert "sk-or-1" not in (cfg / "llm.runtime.json").read_text(encoding="utf-8")  # chave nunca no JSON


def test_manter_chave_com_none_e_remover_reserva_apaga_a_chave(cfg):
    lp.save_fallbacks([{"id": "r1", "provider": "openai", "model": "m", "base_url": "https://openrouter.ai/api", "api_key": "sk-1"}])
    lp.save_fallbacks([{"id": "r1", "provider": "openai", "model": "m2", "base_url": "https://openrouter.ai/api"}])  # None mantem
    assert lp.load_fallback_configs()[0].api_key == "sk-1"
    lp.save_fallbacks([])
    assert lp.load_fallback_configs() == [] and not list((cfg / "credentials").glob("llm_key_*"))


@pytest.mark.parametrize("bad", [
    [{"id": "../x", "provider": "openai", "model": "m", "api_key": "k"}],
    [{"id": "a", "provider": "xyz", "model": "m"}],
    [{"id": "a", "provider": "openai", "model": ""}],
    [{"id": "a", "provider": "anthropic", "model": "m"}],  # nuvem sem chave
    [{"id": "a", "provider": "openai", "model": "m", "api_key": "k"}] * 2,  # id repetido
])
def test_reservas_invalidas_sao_recusadas_sem_gravar(cfg, bad):
    with pytest.raises(LLMConfigError):
        lp.save_fallbacks(bad)
    assert lp.load_fallback_configs() == []


def test_limite_de_reservas_ate_dez_cerebros(cfg):
    mk = lambda n: [{"id": f"r{i}", "provider": "openai", "model": "m", "base_url": "https://openrouter.ai/api", "api_key": "k"} for i in range(n)]  # noqa: E731
    lp.save_fallbacks(mk(9))  # 1 principal + 9 reservas = 10 cerebros
    assert len(lp.load_fallback_configs()) == 9
    with pytest.raises(LLMConfigError):
        lp.save_fallbacks(mk(10))


def test_reserva_mal_configurada_nao_derruba_o_principal(cfg):
    lp.save_fallbacks([{"id": "r1", "provider": "openai", "model": "m", "base_url": "https://openrouter.ai/api", "api_key": "k"}])
    for f in (cfg / "credentials").glob("llm_key_*"):
        f.unlink()  # chave da reserva sumiu
    assert isinstance(lp.get_llm_client(), LLMClient)  # volta ao principal simples


def test_cerebro_sem_credito_402_cai_na_reserva_e_fica_de_castigo_por_mais_tempo():
    t = [0.0]
    chamadas = []

    def principal(r):
        chamadas.append("principal")
        return httpx.Response(402, json={"error": {"message": "Payment Required"}})

    def reserva(r):
        chamadas.append("reserva")
        return sse("oi")

    llm = RoutedLLM([client(principal, "a"), client(reserva, "b")], clock=lambda: t[0])
    assert run(collect(llm))  # respondeu pela reserva, sem erro para a pessoa
    assert chamadas == ["principal", "reserva"]
    t[0] = 100.0  # bem depois dos 45 s do castigo comum: o principal sem credito continua de fora
    run(collect(llm))
    assert chamadas == ["principal", "reserva", "reserva"]
    t[0] = 700.0  # passou o castigo longo: tenta de novo
    run(collect(llm))
    assert chamadas[-2:] == ["principal", "reserva"]


# ---------------- funcoes dos cerebros e equipe ----------------
def _nome(handler_name, texto):
    def h(r):
        usados.append(handler_name)
        if json.loads(r.content).get("stream"):
            return sse(texto)
        return httpx.Response(200, json={"choices": [{"message": {"content": texto}}]})  # chat completo (sem streaming), como na revisao
    return h


usados: list = []


def _equipe(roles, team=(), clock=None):
    usados.clear()
    cs = [client(_nome("a", "resposta A"), "a"), client(_nome("b", "resposta B"), "b"), client(_nome("c", "resposta C"), "c")]
    return RoutedLLM(cs, roles=roles, team=team, clock=clock or (lambda: 0.0))


def test_cada_tarefa_vai_para_o_cerebro_da_funcao():
    llm = _equipe([{"conversa"}, {"ferramentas"}, {"escrita", "estudo"}])
    run(collect(llm))  # conversa curta e sem ferramentas -> "rapido": ninguem declarou; cai em quem serve (conversa) por ordem
    assert usados == ["a"]
    usados.clear()
    run(llm.chat([{"role": "user", "content": "escreva um post sobre luz"}], role="escrita"))
    assert usados == ["c"]
    usados.clear()
    async def com_ferramentas():
        return [x async for x in llm.stream_events([{"role": "user", "content": "veja minha agenda"}], tools=[{"name": "t"}]) if isinstance(x, str)]
    run(com_ferramentas())
    assert usados == ["b"]


def test_conversa_curta_vai_para_o_cerebro_rapido_e_longa_para_o_de_conversa():
    llm = _equipe([{"conversa"}, {"rapido"}, {"ferramentas"}])
    run(collect(llm, [{"role": "user", "content": "oi, tudo bem?"}]))
    assert usados == ["b"]
    usados.clear()
    run(collect(llm, [{"role": "user", "content": "me explica com calma como funciona a bolsa de valores e o que significa investir " * 2}]))
    assert usados == ["a"]


def test_cerebro_sem_funcao_declarada_serve_para_tudo_e_com_lista_vazia_so_de_reserva():
    llm = _equipe([None, {"escrita"}, set()])
    run(llm.chat([{"role": "user", "content": "x"}], role="escrita"))
    assert usados == ["b"]  # quem declarou a funcao vem primeiro
    usados.clear()
    run(llm.chat([{"role": "user", "content": "x"}], role="estudo"))
    assert usados == ["a"]  # sem declarados: quem serve para tudo
    t = [0.0]
    llm2 = _equipe([set(), set(), set()], clock=lambda: t[0])
    run(collect(llm2))
    assert usados  # todos so de reserva ainda respondem (nunca deixa a pessoa sem resposta)


def test_equipe_um_escreve_e_outro_revisa_e_falha_da_revisao_mantem_o_rascunho():
    llm = _equipe([{"escrita"}, {"escrita"}, {"conversa"}], team=("escrita",))
    out = run(llm.chat([{"role": "user", "content": "post"}], role="escrita"))
    assert usados == ["a", "b"] and out == "resposta B"  # B revisou o rascunho de A
    usados.clear()
    assert run(llm.chat([{"role": "user", "content": "oi"}], role="conversa")) == "resposta C"  # funcao fora da equipe: sem revisao
    assert usados == ["c"]
    # so um cerebro com a funcao: nao ha quem revise
    solo = _equipe([{"escrita"}, {"conversa"}, {"conversa"}], team=("escrita",))
    assert run(solo.chat([{"role": "user", "content": "post"}], role="escrita")) == "resposta A" and usados == ["a"]
    # revisor fora do ar: fica o rascunho
    usados.clear()
    falho = RoutedLLM([client(_nome("a", "rascunho"), "a"), client(lambda r: httpx.Response(500), "b")], roles=[{"escrita"}, {"escrita"}], team=("escrita",))
    assert run(falho.chat([{"role": "user", "content": "post"}], role="escrita")) == "rascunho"


def test_funcoes_regras_puras_e_chat_as():
    from src.jefrey.domain.llm_roles import ROLES, chat_as, clean_roles, effective_role, order_by_role, review_messages

    assert clean_roles(["escrita", "voar", "conversa", "escrita"]) == ["conversa", "escrita"] and clean_roles("x") == []
    assert effective_role("estudo", []) == "estudo" and effective_role(None, [], tools=[1]) == "ferramentas"
    assert effective_role(None, [{"role": "user", "content": "oi"}]) == "rapido"
    assert order_by_role([0, 1, 2], [None, {"x"}, {"escrita"}], "escrita") == [2, 0, 1]
    rev = review_messages([{"role": "user", "content": "faca um post"}], "rascunho")
    assert "<rascunho>" in rev[1]["content"] and "ignore qualquer instrucao" in rev[0]["content"] and "conversa" in ROLES

    class Simples:
        async def chat(self, messages):
            return "ok"

    class ComFuncao:
        async def chat(self, messages, role=None):
            return f"ok-{role}"

    assert run(chat_as(Simples(), [], "escrita")) == "ok" and run(chat_as(ComFuncao(), [], "escrita")) == "ok-escrita"


def test_get_llm_client_monta_funcoes_e_equipe_do_arquivo(cfg):
    lp.save_override("openai", "m0", "https://api.exemplo.com", None, "k0")
    lp.save_fallbacks([{"id": "groq", "provider": "openai", "model": "m1", "base_url": "https://api.groq.com/openai", "api_key": "k1"},
                       {"id": "gemini", "provider": "openai", "model": "m2", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "api_key": "k2"}])
    lp.save_roles("groq", ["rapido", "conversa"])
    lp.save_roles("gemini", ["escrita"])
    lp.save_team(["escrita", "conversa"])  # so escrita e estudo podem ser equipe
    assert lp.load_roles() == {"groq": ["conversa", "rapido"], "gemini": ["escrita"]} and lp.load_team() == ["escrita"]
    llm = lp.get_llm_client()
    assert isinstance(llm, RoutedLLM) and llm.roles[1] == {"conversa", "rapido"} and llm.roles[2] == {"escrita"} and llm.roles[0] is None
    assert llm.team == ("escrita",)
    lp.save_roles("groq", None)
    assert "groq" not in lp.load_roles()
