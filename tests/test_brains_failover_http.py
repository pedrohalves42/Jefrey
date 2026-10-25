"""Failover entre cerebros provado por HTTP de verdade: dois servidores locais falam o protocolo OpenAI (streaming SSE)."""
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from src.jefrey.core import llm_provider as P


class Servidor:
    """Servidor local com um 'modo' que pode mudar no meio do teste: ok | 429 | 500 | corta (comeca a resposta e cai)."""

    def __init__(self, nome: str, modo: str = "ok"):
        self.nome, self.modo, self.chamadas = nome, modo, 0
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                outer.chamadas += 1
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                if outer.modo in ("429", "500"):
                    self.send_response(int(outer.modo))
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                partes = [f"resposta do {outer.nome}", " continua"]
                for i, p in enumerate(partes):
                    self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': p}}]})}\n\n".encode())
                    self.wfile.flush()
                    if outer.modo == "corta" and i == 0:
                        self.connection.close()  # cai no meio da resposta
                        return
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def cfg(self) -> P.LLMConfig:
        return P.LLMConfig("openai", "m", f"http://127.0.0.1:{self.port}/v1", "chave-de-teste")

    def parar(self):
        self.srv.shutdown()
        self.srv.server_close()


@pytest.fixture()
def dois():
    a, b = Servidor("principal"), Servidor("reserva")
    yield a, b
    a.parar()
    b.parar()


def roteador(a, b, relogio):
    return P.RoutedLLM([P.LLMClient(a.cfg()), P.LLMClient(b.cfg())], clock=relogio)


def run(coro):
    return asyncio.run(coro)


async def pergunta(r):
    return "".join([x async for x in r.stream([{"role": "user", "content": "oi"}])])


def test_tudo_bem_responde_o_principal(dois):
    a, b = dois
    assert run(pergunta(roteador(a, b, lambda: 0.0))) == "resposta do principal continua"
    assert b.chamadas == 0


@pytest.mark.parametrize("falha", ["429", "500"])
def test_principal_cai_reserva_responde(dois, falha):
    a, b = dois
    a.modo = falha
    r = roteador(a, b, lambda: 0.0)
    assert run(pergunta(r)) == "resposta do reserva continua"
    assert a.chamadas == 1 and b.chamadas == 1 and "openai" in r.last_label


def test_principal_fora_do_ar_conexao_recusada(dois):
    a, b = dois
    a.parar()  # ninguem escutando: ConnectError
    assert run(pergunta(roteador(a, b, lambda: 0.0))) == "resposta do reserva continua"


def test_resposta_ja_iniciada_nao_troca_de_cerebro(dois):
    a, b = dois
    a.modo = "corta"
    r = roteador(a, b, lambda: 0.0)
    try:
        texto = run(pergunta(r))  # a conexao cai depois do primeiro pedaco: a resposta termina ali
    except Exception:
        texto = ""  # (ou levanta erro: tambem vale)
    assert "reserva" not in texto  # nunca mistura duas vozes na mesma resposta
    assert b.chamadas == 0


def test_cooldown_de_45s_e_respeitado(dois):
    a, b = dois
    a.modo = "500"
    t = [1000.0]
    r = roteador(a, b, lambda: t[0])
    run(pergunta(r))
    assert a.chamadas == 1
    a.modo = "ok"
    run(pergunta(r))  # ainda em descanso: nem tenta o principal
    assert a.chamadas == 1 and b.chamadas == 2
    t[0] += P.COOLDOWN_S + 1
    assert run(pergunta(r)) == "resposta do principal continua" and a.chamadas == 2


def test_todos_falham_levanta_erro_com_frase_simples(dois):
    a, b = dois
    a.modo = b.modo = "500"
    r = roteador(a, b, lambda: 0.0)
    with pytest.raises(Exception) as e:
        run(pergunta(r))
    assert P.friendly_error(e.value)  # a tela recebe uma frase em portugues, nunca o erro cru
    assert "Traceback" not in P.friendly_error(e.value) and "http://" not in P.friendly_error(e.value)
