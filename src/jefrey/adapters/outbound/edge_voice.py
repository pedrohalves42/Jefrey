"""Voz natural GRATUITA na nuvem (vozes neurais da Microsoft, as mesmas do navegador Edge): sem conta, sem chave, sem saldo.

Aviso de privacidade: o texto que o Jefrey vai FALAR e enviado ao servico de voz da Microsoft (como acontece com o cerebro na nuvem).
Se ficar fora do ar ou sem internet, o motor se "esfria" por 2 minutos e o Jefrey fala com a voz do computador.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# id do motor -> (voz da Microsoft, nome para a pessoa)
VOICES: dict[str, tuple[str, str]] = {
    "edge": ("pt-BR-ThalitaMultilingualNeural", "Thalita (mulher, animada)"),
    "edge-francisca": ("pt-BR-FranciscaNeural", "Francisca (mulher, clara)"),
    "edge-antonio": ("pt-BR-AntonioNeural", "Antônio (homem)"),
}
RATE = "+8%"  # um pouco mais vivo que o normal: menos "GPS", mais animado
PITCH = "+3Hz"
MAX_CHARS = 700
TIMEOUT_S = 15.0
COOL_S = 120.0

_cool_until = 0.0


class EdgeVoiceError(Exception):
    """Mensagem em portugues simples."""


def engine_ids() -> list[str]:
    return list(VOICES)


def available(now: Optional[float] = None) -> bool:
    t = time.monotonic() if now is None else now
    if t < _cool_until:
        return False
    try:
        import edge_tts  # noqa: F401
    except Exception:
        return False
    return True


def _clean(text: str) -> str:
    return " ".join((text or "").replace("​", " ").split())[:MAX_CHARS]


async def synth(text: str, engine: str = "edge", *, communicate=None) -> bytes:
    """MP3 com a fala. `communicate` existe para teste (troca a conexao real por uma falsa)."""
    global _cool_until
    voice = VOICES.get(engine, VOICES["edge"])[0]
    clean = _clean(text)
    if not clean:
        raise EdgeVoiceError("Não há o que falar.")
    try:
        if communicate is None:
            import edge_tts

            communicate = edge_tts.Communicate

        async def run() -> bytes:
            out = bytearray()
            async for chunk in communicate(clean, voice, rate=RATE, pitch=PITCH).stream():
                if chunk.get("type") == "audio":
                    out += chunk["data"]
            return bytes(out)

        audio = await asyncio.wait_for(run(), timeout=TIMEOUT_S)
    except Exception as e:
        _cool_until = time.monotonic() + COOL_S
        logger.info("voz gratuita da nuvem falhou (%s)", type(e).__name__)
        raise EdgeVoiceError("Não consegui a voz gratuita da nuvem agora. Vou usar a do computador.")
    if len(audio) < 500:
        _cool_until = time.monotonic() + COOL_S
        raise EdgeVoiceError("A voz gratuita da nuvem não respondeu direito. Vou usar a do computador.")
    return audio


def reset_cooldown() -> None:
    global _cool_until
    _cool_until = 0.0
