"""Voz do Gemini: WAV valido, chave so no cabecalho, esfria no limite, nunca vaza a chave."""
import asyncio
import base64
import io
import wave

import httpx
import pytest

from src.jefrey.adapters.outbound import gemini_voice as GV

PCM = b"\x01\x02" * 4000


def ok_body():
    return {"candidates": [{"content": {"parts": [{"inlineData": {"data": base64.b64encode(PCM).decode()}}]}}]}


@pytest.fixture(autouse=True)
def limpa():
    GV.reset_cooldown()
    yield
    GV.reset_cooldown()


def run(handler, text="Bom dia, Pedro."):
    return asyncio.run(GV.synth(text, key="chave-secreta-123", transport=httpx.MockTransport(handler)))


def test_devolve_wav_valido_e_manda_a_chave_no_cabecalho():
    seen = {}

    def h(req):
        seen["url"], seen["key"], seen["body"] = str(req.url), req.headers.get("x-goog-api-key"), req.content.decode()
        return httpx.Response(200, json=ok_body())

    wav = run(h)
    with wave.open(io.BytesIO(wav)) as w:
        assert w.getframerate() == 24_000 and w.getnchannels() == 1 and w.getnframes() == len(PCM) // 2
    assert seen["key"] == "chave-secreta-123" and "chave-secreta" not in seen["url"]
    assert "Charon" in seen["body"] and "Bom dia, Pedro." in seen["body"]


def test_segundo_modelo_quando_o_primeiro_da_limite():
    calls = []

    def h(req):
        calls.append(str(req.url))
        return httpx.Response(429, json={}) if len(calls) == 1 else httpx.Response(200, json=ok_body())

    assert run(h)[:4] == b"RIFF" and len(calls) == 2


def test_limite_em_todos_esfria_e_diz_com_clareza():
    with pytest.raises(GV.GeminiVoiceError) as e:
        run(lambda req: httpx.Response(429, json={}))
    assert "limite" in str(e.value) and "chave-secreta" not in str(e.value)
    assert GV.available(key="x") is False  # esfriou: o Jefrey usa a voz seguinte


def test_chave_sem_acesso_esfria_por_mais_tempo():
    with pytest.raises(GV.GeminiVoiceError):
        run(lambda req: httpx.Response(403, json={}))
    assert GV.available(key="x") is False


def test_audio_vazio_ou_resposta_estranha_nao_vira_fala():
    with pytest.raises(GV.GeminiVoiceError):
        run(lambda req: httpx.Response(200, json={"candidates": []}))


def test_texto_vazio_e_sem_chave():
    with pytest.raises(GV.GeminiVoiceError):
        asyncio.run(GV.synth("  ", key="k"))
    with pytest.raises(GV.GeminiVoiceError):
        asyncio.run(GV.synth("oi", key=""))
