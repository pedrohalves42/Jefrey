import asyncio

import pytest
from fastapi import HTTPException

from src.jefrey.api import voice_routes as VR
from src.jefrey.core import cloudvoice as CV
from src.jefrey.core import localvoice as LV


def run(c):
    return asyncio.run(c)


class Req:
    def __init__(self, uid="ana"):
        self.state = type("S", (), {"user_id": uid})()


@pytest.fixture(autouse=True)
def limpo(monkeypatch):
    VR._download.update(state="idle", pct=0, error="")


def _engines(monkeypatch, cloud=False, local=False):
    monkeypatch.setattr(CV, "available", lambda: cloud)
    monkeypatch.setattr(LV, "available", lambda: local)


def test_padrao_prefere_nuvem_depois_local_depois_navegador(monkeypatch):
    _engines(monkeypatch, cloud=True, local=True)
    assert run(VR.engines(Req()))["default"] == "cloud"
    _engines(monkeypatch, cloud=False, local=True)
    assert run(VR.engines(Req()))["default"] == "local"
    _engines(monkeypatch)
    out = run(VR.engines(Req()))
    assert out["default"] == "browser" and {e["id"] for e in out["engines"]} == {"cloud", "local", "browser"}
    assert [e for e in out["engines"] if e["id"] == "browser"][0]["available"] is True


def test_sem_login_401():
    with pytest.raises(HTTPException) as e:
        run(VR.engines(Req(uid="anonymous")))
    assert e.value.status_code == 401
    with pytest.raises(HTTPException) as e:
        run(VR.speak(Req(uid=None), VR.SpeakBody(text="oi")))
    assert e.value.status_code == 401


def test_falha_da_nuvem_cai_para_o_local(monkeypatch):
    _engines(monkeypatch, cloud=True, local=True)

    async def nuvem_fora(text, **k):
        raise CV.CloudVoiceError("sem saldo")
    monkeypatch.setattr(CV, "synth", nuvem_fora)
    monkeypatch.setattr(LV, "synth", lambda t: b"RIFFwav")
    r = run(VR.speak(Req(), VR.SpeakBody(text="oi")))
    assert r.body == b"RIFFwav" and r.media_type == "audio/wav" and r.headers["x-voice-engine"] == "local"


def test_nuvem_responde_mp3(monkeypatch):
    _engines(monkeypatch, cloud=True, local=True)

    async def nuvem(text, **k):
        return b"ID3mp3"
    monkeypatch.setattr(CV, "synth", nuvem)
    r = run(VR.speak(Req(), VR.SpeakBody(text="oi")))
    assert r.media_type == "audio/mpeg" and r.headers["x-voice-engine"] == "cloud"


def test_nenhum_motor_devolve_409_simples(monkeypatch):
    _engines(monkeypatch)
    with pytest.raises(HTTPException) as e:
        run(VR.speak(Req(), VR.SpeakBody(text="oi")))
    assert e.value.status_code == 409 and "computador" in e.value.detail


def test_motor_pedido_indisponivel_e_recusado(monkeypatch):
    _engines(monkeypatch, cloud=False, local=True)
    with pytest.raises(HTTPException) as e:
        run(VR.speak(Req(), VR.SpeakBody(text="oi", engine="cloud")))
    assert e.value.status_code == 409


def test_texto_e_limitado():
    with pytest.raises(Exception):
        VR.SpeakBody(text="a" * 2001)
    with pytest.raises(Exception):
        VR.SpeakBody(text="")


def test_download_acompanha_progresso_e_erro(monkeypatch):
    async def baixa(progress=None, **k):
        for p in (10, 60, 100):
            progress(p)
    monkeypatch.setattr(LV, "download_model", baixa)

    async def fluxo():
        await VR.start_download(Req())
        await VR._task
        return await VR.local_status(Req())
    s = run(fluxo())
    assert s["state"] == "done" and s["pct"] == 100

    async def quebra(progress=None, **k):
        raise LV.LocalVoiceError("Sem internet.")
    monkeypatch.setattr(LV, "download_model", quebra)

    async def fluxo2():
        await VR.start_download(Req())
        await VR._task
        return await VR.local_status(Req())
    s = run(fluxo2())
    assert s["state"] == "error" and s["error"] == "Sem internet."
