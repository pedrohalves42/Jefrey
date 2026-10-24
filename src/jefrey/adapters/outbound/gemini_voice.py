"""Voz natural do Gemini (Google): voz masculina grave e calma, bem menos robotica que as vozes antigas do computador.

Usa a MESMA chave do Gemini que a pessoa ja conectou como cerebro (nada novo para configurar).
Aviso de privacidade: o texto que o Jefrey vai FALAR vai ao Google, como o texto das conversas ja vai quando o Gemini e o cerebro.
Limite do plano gratuito (429): o motor se "esfria" e o Jefrey usa a voz seguinte (Microsoft gratuita, depois a do computador).
"""
from __future__ import annotations

import base64
import io
import logging
import time
import wave
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MODELS = ("gemini-2.5-flash-preview-tts", "gemini-3.1-flash-tts-preview")
VOICE = "Charon"  # masculina, grave e calma
STYLE = "Diga em português do Brasil, com voz masculina grave, calma e natural, num ritmo confortável: "
SAMPLE_RATE = 24_000
MAX_CHARS = 700
TIMEOUT_S = 25.0
COOL_RATE_S = 120.0
COOL_DENIED_S = 600.0

_cool_until = 0.0


class GeminiVoiceError(Exception):
    """Mensagem em portugues simples."""


def _key() -> Optional[str]:
    from src.jefrey.adapters.outbound import llm_provider as P
    from src.jefrey.adapters.outbound.secret_store import read_secret

    key = read_secret(P._fallback_key_file("gemini"))
    if key:
        return key
    try:
        if "generativelanguage" in str(P.config_from_settings().base_url):
            return P.load_saved_key()
    except Exception:
        logger.debug("chave do gemini indisponivel", exc_info=True)
    return None


def available(now: Optional[float] = None, key: Optional[str] = None) -> bool:
    t = time.monotonic() if now is None else now
    if t < _cool_until:
        return False
    return bool(key if key is not None else _key())


def _wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


def _clean(text: str) -> str:
    return " ".join((text or "").replace("​", " ").split())[:MAX_CHARS]


async def synth(text: str, *, key: Optional[str] = None, transport: Optional[httpx.AsyncBaseTransport] = None) -> bytes:
    """WAV com a fala. `transport` existe para teste."""
    global _cool_until
    clean = _clean(text)
    if not clean:
        raise GeminiVoiceError("Não há o que falar.")
    api_key = key or _key()
    if not api_key:
        raise GeminiVoiceError("O Gemini não está conectado.")
    body = {"contents": [{"parts": [{"text": STYLE + clean}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}}
    last = "A voz do Gemini não respondeu agora."
    async with httpx.AsyncClient(timeout=TIMEOUT_S, transport=transport) as c:
        for model in MODELS:
            try:
                r = await c.post(URL.format(model=model), headers={"x-goog-api-key": api_key}, json=body)  # chave no cabecalho, nunca na URL
            except httpx.HTTPError as e:
                logger.info("voz gemini: rede (%s)", type(e).__name__)
                continue
            if r.status_code == 200:
                try:
                    pcm = base64.b64decode(r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
                except (KeyError, IndexError, ValueError, TypeError):
                    continue
                if len(pcm) > 2000:
                    return _wav(pcm)
                continue
            if r.status_code in (401, 403):
                _cool_until = time.monotonic() + COOL_DENIED_S
                raise GeminiVoiceError("A chave do Gemini não tem acesso à voz.")
            if r.status_code == 429:
                last = "A voz do Gemini atingiu o limite do plano agora."
                continue
            logger.info("voz gemini: HTTP %s", r.status_code)
    _cool_until = time.monotonic() + COOL_RATE_S
    raise GeminiVoiceError(last)


def reset_cooldown() -> None:
    global _cool_until
    _cool_until = 0.0
