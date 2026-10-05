import asyncio
import hashlib
import io
import wave

import httpx
import pytest

from src.jefrey.core import localvoice as LV


def run(c):
    return asyncio.run(c)


@pytest.fixture(autouse=True)
def casa(tmp_path, monkeypatch):
    monkeypatch.setenv("JEFREY_DATA_DIR", str(tmp_path))
    LV._cache.clear()


def _arquivos(monkeypatch, modelo=b"M" * 1000, config=b'{"audio": {"sample_rate": 22050}}'):
    """Faz o modulo esperar estes dois 'arquivos' (tamanho e hash batendo) em vez dos reais (63 MB)."""
    monkeypatch.setattr(LV, "FILES", {
        "model": {"name": "v.onnx", "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/x.onnx", "sha256": hashlib.sha256(modelo).hexdigest(), "size": len(modelo)},
        "config": {"name": "v.onnx.json", "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/x.json", "sha256": hashlib.sha256(config).hexdigest(), "size": len(config)},
    })
    return modelo, config


def _transport(modelo, config):
    return httpx.MockTransport(lambda r: httpx.Response(200, content=modelo if r.url.path.endswith("onnx") else config))


def test_enderecos_do_modelo_sao_fixos_e_oficiais():
    for f in LV.FILES.values():
        assert f["url"].startswith("https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/")
        assert len(f["sha256"]) == 64 and f["size"] > 1000


def test_sem_modelo_status_e_synth_explicam():
    assert LV.model_status()["installed"] is False
    assert LV.available() is False
    with pytest.raises(LV.LocalVoiceError, match="Baixe"):
        LV.synth("oi")


def test_modelo_so_instala_se_sha256_confere(monkeypatch):
    modelo, config = _arquivos(monkeypatch)
    ruim = httpx.MockTransport(lambda r: httpx.Response(200, content=b"X" * len(modelo) if r.url.path.endswith("onnx") else config))
    with pytest.raises(LV.LocalVoiceError, match="não confere"):
        run(LV.download_model(transport=ruim))
    assert LV.model_status()["installed"] is False
    assert not list(LV.voices_dir().glob("*.part"))  # nada pela metade fica no disco


def test_download_bom_instala_e_reporta_progresso(monkeypatch):
    modelo, config = _arquivos(monkeypatch)
    passos = []
    run(LV.download_model(progress=passos.append, transport=_transport(modelo, config)))
    assert LV.model_status()["installed"] is True and LV.model_status()["size_mb"] >= 0
    assert passos and passos[-1] == 100 and passos == sorted(passos)


def test_download_recusa_desvio_para_endereco_inseguro(monkeypatch):
    modelo, config = _arquivos(monkeypatch)

    def handler(r):
        return httpx.Response(302, headers={"location": "http://evil.example/x"}) if r.url.host == "huggingface.co" else httpx.Response(200, content=modelo)
    with pytest.raises(LV.LocalVoiceError):
        run(LV.download_model(transport=httpx.MockTransport(handler)))
    assert LV.model_status()["installed"] is False


def test_texto_longo_e_cortado_e_wav_valido(monkeypatch):
    modelo, config = _arquivos(monkeypatch)
    run(LV.download_model(transport=_transport(modelo, config)))
    ouvido = []

    class Falsa:
        def synthesize_wav(self, text, wav):
            ouvido.append(text)
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(22050)
            wav.writeframes(b"\x00\x00" * 100)
    monkeypatch.setattr(LV, "_load", lambda: Falsa())
    wav = LV.synth("a " * 2000)
    assert len(ouvido[0]) <= LV.MAX_CHARS
    with wave.open(io.BytesIO(wav)) as w:
        assert w.getframerate() == 22050 and w.getnframes() == 100


def test_texto_vazio_e_recusado(monkeypatch):
    modelo, config = _arquivos(monkeypatch)
    run(LV.download_model(transport=_transport(modelo, config)))
    with pytest.raises(LV.LocalVoiceError, match="falar"):
        LV.synth("   ")
