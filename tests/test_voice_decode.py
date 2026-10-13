"""Regressao: o Whisper local precisa decodificar audio. Com `av` novo demais a transcricao quebrava (erro 500 em /stt)."""
import io
import math
import struct
import wave

import pytest


def _wav(seconds=0.6, rate=16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(int(rate * seconds))))
    return buf.getvalue()


def test_faster_whisper_consegue_decodificar_audio():
    audio = pytest.importorskip("faster_whisper.audio")
    pytest.importorskip("av")
    samples = audio.decode_audio(io.BytesIO(_wav()), sampling_rate=16000)
    assert len(samples) > 8000  # ~0,6 s a 16 kHz


def test_versao_do_av_esta_na_faixa_que_funciona():
    av = pytest.importorskip("av")
    major = int(av.__version__.split(".")[0])
    assert 14 <= major < 17, f"av {av.__version__} nao foi validado com o faster-whisper"
