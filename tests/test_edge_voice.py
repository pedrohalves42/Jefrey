"""Voz gratuita da nuvem: conexao falsa (sem internet), esfriamento depois de falha e escolha do motor padrao."""
import asyncio

import pytest

from src.jefrey.adapters.outbound import edge_voice as EV


def run(c):
    return asyncio.run(c)


@pytest.fixture(autouse=True)
def limpo():
    EV.reset_cooldown()
    yield
    EV.reset_cooldown()


class Falsa:
    ultima = {}

    def __init__(self, text, voice, rate=None, pitch=None, **k):
        Falsa.ultima = {"text": text, "voice": voice, "rate": rate, "pitch": pitch}

    async def stream(self):
        yield {"type": "WordBoundary", "text": "x"}
        yield {"type": "audio", "data": b"A" * 400}
        yield {"type": "audio", "data": b"B" * 400}


class Quebrada(Falsa):
    async def stream(self):
        raise ConnectionError("sem internet")
        yield {}


def test_gera_audio_com_a_voz_certa_e_ritmo_animado():
    audio = run(EV.synth("  Bom   dia, Pedro!  ", "edge-antonio", communicate=Falsa))
    assert audio == b"A" * 400 + b"B" * 400
    assert Falsa.ultima == {"text": "Bom dia, Pedro!", "voice": "pt-BR-AntonioNeural", "rate": EV.RATE, "pitch": EV.PITCH}
    run(EV.synth("Oi", "edge", communicate=Falsa))
    assert Falsa.ultima["voice"] == "pt-BR-ThalitaMultilingualNeural"
    run(EV.synth("Oi", "qualquer-coisa", communicate=Falsa))  # id desconhecido cai na voz padrao
    assert Falsa.ultima["voice"] == "pt-BR-ThalitaMultilingualNeural"


def test_texto_enorme_e_cortado_e_vazio_e_recusado():
    run(EV.synth("a " * 2000, communicate=Falsa))
    assert len(Falsa.ultima["text"]) <= EV.MAX_CHARS
    with pytest.raises(EV.EdgeVoiceError):
        run(EV.synth("   ", communicate=Falsa))


def test_falha_esfria_o_motor_por_dois_minutos_e_volta_depois():
    assert EV.available()
    with pytest.raises(EV.EdgeVoiceError) as e:
        run(EV.synth("Oi", communicate=Quebrada))
    assert "do computador" in str(e.value) and "sem internet" not in str(e.value)
    assert not EV.available()
    assert EV.available(now=__import__("time").monotonic() + EV.COOL_S + 1)


def test_resposta_vazia_tambem_conta_como_falha():
    class Vazia(Falsa):
        async def stream(self):
            yield {"type": "audio", "data": b"x"}

    with pytest.raises(EV.EdgeVoiceError):
        run(EV.synth("Oi", communicate=Vazia))
    assert not EV.available()


def test_padrao_do_servidor_e_a_voz_gratuita_e_a_conta_paga_so_por_escolha(monkeypatch):
    from src.jefrey.api import voice_routes as VR

    class Req:
        class state:
            user_id = "ana"

    monkeypatch.setattr(VR.CV, "available", lambda: True)
    monkeypatch.setattr(VR.LV, "available", lambda: True)
    monkeypatch.setattr(VR.LV, "_cache", {"voice": 1})
    out = run(VR.engines(Req()))
    ids = {e["id"]: e["available"] for e in out["engines"]}
    assert out["default"] == "edge" and ids["edge"] and ids["edge-francisca"] and ids["edge-antonio"] and ids["cloud"] and ids["local"]
    EV._cool_until = __import__("time").monotonic() + 100  # fora do ar: cai para a voz natural do computador
    assert run(VR.engines(Req()))["default"] == "local"


def test_build_inclui_a_voz_gratuita():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    assert "edge-tts" in (root / "requirements.txt").read_text(encoding="utf-8")
    assert "--collect-all edge_tts" in (root / "packaging" / "build_exe.bat").read_text(encoding="utf-8")
