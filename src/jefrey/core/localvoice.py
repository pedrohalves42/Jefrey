"""Voz local neural (Piper): fala natural, sem internet e sem enviar o texto para fora.

O modelo (~60 MB) NAO vai no instalador: e baixado uma vez, com o botao "Baixar voz natural". Os enderecos e os SHA-256 ficam
fixos aqui; um arquivo que nao confere e apagado e nada e usado.
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
import wave
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger(__name__)

VOICE = "pt_BR-faber-medium"
_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/"
FILES: dict[str, dict] = {
    "model": {"name": f"{VOICE}.onnx", "url": _BASE + f"{VOICE}.onnx", "size": 63_201_294,
              "sha256": "858555e3a064209c57088fe6bd70c4c3dc54d03eaa00c45d5ecaf43a33f95aa7"},
    "config": {"name": f"{VOICE}.onnx.json", "url": _BASE + f"{VOICE}.onnx.json", "size": 4_855,
               "sha256": "7e694de195ae3fc36dd732c445eb04fb49b649854893cb5506b978f0d50a1d6f"},
}
MAX_CHARS = 700
# Mais variacao e um pouco mais calma que o padrao do modelo (0,667 / 1,0 / 0,8): menos "voz de GPS", mais natural.
PROSODY = {"length_scale": 1.04, "noise_scale": 0.78, "noise_w_scale": 0.95}
CHUNK = 1024 * 256
_cache: dict = {}


class LocalVoiceError(Exception):
    """Mensagem em portugues simples, pronta para a tela."""


def voices_dir() -> Path:
    base = os.getenv("JEFREY_DATA_DIR")
    root = Path(base) if base else Path(os.getenv("JEFREY_FILES_DIR", "data/files")).parent
    return root / "voices"


def _path(key: str) -> Path:
    return voices_dir() / FILES[key]["name"]


def model_status() -> dict:
    ok = all(_path(k).is_file() and _path(k).stat().st_size == FILES[k]["size"] for k in FILES)
    return {"installed": ok, "size_mb": round(sum(f["size"] for f in FILES.values()) / (1024 * 1024)), "voice": VOICE}


def available() -> bool:
    if not model_status()["installed"]:
        return False
    try:
        import piper  # noqa: F401
    except Exception as e:
        logger.info("voz local: piper indisponivel (%s)", type(e).__name__)
        return False
    return True


async def download_model(progress: Optional[Callable[[int], None]] = None, *, transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
    """Baixa e confere (tamanho + SHA-256) os dois arquivos. `progress` recebe 0..100."""
    voices_dir().mkdir(parents=True, exist_ok=True)
    total = sum(f["size"] for f in FILES.values())
    done = 0
    last = -1
    try:
        async with httpx.AsyncClient(timeout=60, transport=transport, follow_redirects=True) as c:
            for key, f in FILES.items():
                dest, part = _path(key), _path(key).with_suffix(_path(key).suffix + ".part")
                h, got = hashlib.sha256(), 0
                try:
                    async with c.stream("GET", f["url"]) as r:
                        if r.status_code != 200:
                            raise LocalVoiceError("Não consegui baixar a voz agora. Verifique a internet e tente de novo.")
                        if urlsplit(str(r.url)).scheme != "https":
                            raise LocalVoiceError("O download foi desviado para um endereço inseguro. Não vou usar.")
                        with part.open("wb") as out:
                            async for chunk in r.aiter_bytes(CHUNK):
                                got += len(chunk)
                                if got > f["size"]:
                                    raise LocalVoiceError("O arquivo da voz é maior do que o esperado. Não vou usar.")
                                h.update(chunk)
                                out.write(chunk)
                                done += len(chunk)
                                pct = min(99, int(done * 100 / total))
                                if progress and pct != last:
                                    last = pct
                                    progress(pct)
                    if got != f["size"] or h.hexdigest() != f["sha256"]:
                        raise LocalVoiceError("O arquivo da voz baixado não confere com o esperado. Não vou usar.")
                    part.replace(dest)
                finally:
                    part.unlink(missing_ok=True)
    except LocalVoiceError:
        _purge()
        raise
    except httpx.HTTPError as e:
        logger.info("voz local: download falhou (%s)", type(e).__name__)
        _purge()
        raise LocalVoiceError("Não consegui baixar a voz agora. Verifique a internet e tente de novo.")
    _cache.clear()
    if progress:
        progress(100)


def _purge() -> None:
    for k in FILES:
        _path(k).unlink(missing_ok=True)


def _load():
    v = _cache.get("voice")
    if v is None:
        from piper import PiperVoice

        v = PiperVoice.load(_path("model"), _path("config"))
        _cache["voice"] = v
    return v


def synth(text: str) -> bytes:
    """WAV com a fala. Levanta LocalVoiceError em portugues simples."""
    t = " ".join((text or "").split())[:MAX_CHARS]
    if not t:
        raise LocalVoiceError("Não há o que falar.")
    if not model_status()["installed"]:
        raise LocalVoiceError("Baixe a voz natural em Configurações para usar a voz do computador.")
    try:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            from piper.config import SynthesisConfig

            _load().synthesize_wav(t, w, syn_config=SynthesisConfig(**PROSODY))
        return buf.getvalue()
    except LocalVoiceError:
        raise
    except Exception as e:
        logger.warning("voz local: falhou ao falar (%s)", type(e).__name__)
        raise LocalVoiceError("Não consegui falar com a voz natural agora.")
