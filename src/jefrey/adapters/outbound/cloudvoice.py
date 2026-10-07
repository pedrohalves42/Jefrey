"""Voz natural na nuvem, usando a conta do ChatGPT (OpenAI) que a pessoa ja conectou como cerebro.

Sem essa conta conectada, nada acontece e a tela usa as vozes do computador. O texto falado vai para a OpenAI (a mesma conta do
cerebro); a chave nunca sai do servidor. Texto limitado por pedido para o custo ficar previsivel.
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

URL = "https://api.openai.com/v1/audio/speech"  # endereco fixo: nada vindo de fora decide para onde a chave vai
MODEL = "gpt-4o-mini-tts"
VOICE = "nova"
MAX_CHARS = 700
STYLE = ("Fale em português do Brasil com energia e entusiasmo de verdade, voz confiante e firme, sorrindo ao falar. "
         "Ritmo animado e fluido, sem pausas arrastadas; varie a entonação e destaque as palavras importantes. "
         "Soe como um amigo seguro de si dando uma boa notícia, nunca monótono, robótico ou lento.")


class CloudVoiceError(Exception):
    """Mensagem em portugues simples."""


def _key() -> str:
    try:
        from src.jefrey.core import brains

        for e in brains._entries():
            if e.get("id") == "openai" and e.get("api_key"):
                return str(e["api_key"])
    except Exception as e:
        logger.debug("voz na nuvem: sem acesso as chaves (%s)", type(e).__name__)
    return ""


def available() -> bool:
    return bool(_key())


async def synth(text: str, *, transport: httpx.AsyncBaseTransport | None = None) -> bytes:
    key = _key()
    if not key:
        raise CloudVoiceError("Conecte o ChatGPT em Conexões para usar a voz natural.")
    text = " ".join((text or "").split())[:MAX_CHARS]
    if not text:
        raise CloudVoiceError("Não há o que falar.")
    try:
        async with httpx.AsyncClient(timeout=30, transport=transport, follow_redirects=False) as c:
            r = await c.post(URL, headers={"Authorization": f"Bearer {key}"},
                             json={"model": MODEL, "voice": VOICE, "input": text, "instructions": STYLE, "response_format": "mp3"})
    except Exception as e:
        logger.info("voz na nuvem falhou (%s)", type(e).__name__)
        raise CloudVoiceError("Não consegui a voz da nuvem agora. Vou usar a do computador.")
    if r.status_code in (401, 403):
        raise CloudVoiceError("A conta do ChatGPT não aceitou a voz. Confira o código em Conexões.")
    if r.status_code == 429:
        raise CloudVoiceError("A conta do ChatGPT está sem saldo ou no limite agora.")
    if r.status_code != 200 or not r.content:
        raise CloudVoiceError("Não consegui a voz da nuvem agora. Vou usar a do computador.")
    return r.content
