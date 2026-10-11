import asyncio
import json

import httpx
import pytest

from src.jefrey.core import cloudvoice as CV


def run(c):
    return asyncio.run(c)


def _with_key(monkeypatch, key="sk-teste-123"):
    from src.jefrey.core import brains
    monkeypatch.setattr(brains, "_entries", lambda: [{"id": "openai", "api_key": key}, {"id": "groq", "api_key": "gsk_x"}] if key else [])


def test_sem_chatgpt_conectado_nao_ha_voz_na_nuvem(monkeypatch):
    _with_key(monkeypatch, "")
    assert CV.available() is False
    with pytest.raises(CV.CloudVoiceError, match="ChatGPT"):
        run(CV.synth("oi"))


def test_pedido_vai_so_para_a_openai_com_a_chave_certa(monkeypatch):
    _with_key(monkeypatch)
    vistos = []

    def handler(req: httpx.Request):
        vistos.append(req)
        return httpx.Response(200, content=b"ID3audio")
    out = run(CV.synth("Oi, tudo bem?", transport=httpx.MockTransport(handler)))
    assert out == b"ID3audio" and len(vistos) == 1
    r = vistos[0]
    assert str(r.url) == "https://api.openai.com/v1/audio/speech"
    assert r.headers["authorization"] == "Bearer sk-teste-123"
    body = json.loads(r.content)
    assert body["input"] == "Oi, tudo bem?" and body["response_format"] == "mp3" and "português" in body["instructions"]


def test_texto_longo_e_cortado_para_controlar_custo(monkeypatch):
    _with_key(monkeypatch)
    enviado = []
    run(CV.synth("a " * 2000, transport=httpx.MockTransport(lambda r: (enviado.append(json.loads(r.content)["input"]), httpx.Response(200, content=b"x"))[1])))
    assert len(enviado[0]) <= CV.MAX_CHARS


@pytest.mark.parametrize("status,trecho", [(401, "código"), (429, "saldo"), (500, "computador")])
def test_erros_viram_frases_simples(monkeypatch, status, trecho):
    _with_key(monkeypatch)
    with pytest.raises(CV.CloudVoiceError, match=trecho):
        run(CV.synth("oi", transport=httpx.MockTransport(lambda r: httpx.Response(status, text="detalhe interno com sk-teste-123"))))


def test_erro_nao_vaza_a_chave(monkeypatch):
    _with_key(monkeypatch)
    try:
        run(CV.synth("oi", transport=httpx.MockTransport(lambda r: httpx.Response(401, text="sk-teste-123"))))
    except CV.CloudVoiceError as e:
        assert "sk-teste" not in str(e)
