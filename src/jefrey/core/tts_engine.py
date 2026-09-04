"""P1.1 — TTS Engine (Axiom #1 FAIL-CLOSED, ElevenLabs + pyttsx3 fallback, CIPHER-035)."""
from __future__ import annotations
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

def _tts_provider() -> str:
    try:
        from src.jefrey.core.config import get_settings
        return getattr(get_settings().voice.tts, "provider", "piper")
    except Exception:
        return "piper"

def _eleven_key() -> str:
    return os.getenv("JEFREY_TTS__API_KEY", "") or os.getenv("ELEVENLABS_API_KEY", "")

class TTSEngine:
    """TTS: ElevenLabs se key presente, senão pyttsx3/píper fallback; nunca inventa áudio."""
    def synthesize(self, text: str, voice_id: Optional[str] = None) -> bytes:
        if not text or not text.strip():
            raise ValueError("texto vazio para TTS")
        if len(text) > 5000:
            raise ValueError("texto muito longo (>5000 chars)")

        provider = _tts_provider()
        # Try ElevenLabs if configured
        if provider == "elevenlabs" and _eleven_key():
            try:
                from elevenlabs.client import ElevenLabs
                client = ElevenLabs(api_key=_eleven_key())
                vid = voice_id or "21m00Tcm4TlvDq8ikWAM"  # Rachel default
                audio = client.text_to_speech.convert(text=text, voice_id=vid, model_id="eleven_multilingual_v2", output_format="mp3_44100_128")
                # audio is iterator
                data = b"".join(chunk for chunk in audio)
                if data:
                    return data
            except Exception as e:
                logger.warning("ElevenLabs TTS falhou, fallback: %s", e)

        # Fallback pyttsx3 -> wav bytes via temp file
        try:
            import pyttsx3
            import tempfile
            engine = pyttsx3.init()
            # speed via config
            try:
                from src.jefrey.core.config import get_settings
                speed = float(getattr(get_settings().voice.tts, "speed", 1.0))
                rate = engine.getProperty("rate")
                engine.setProperty("rate", int(rate * speed))
            except Exception:
                pass
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
            engine.save_to_file(text, tmp_path)
            engine.runAndWait()
            with open(tmp_path, "rb") as f:
                data = f.read()
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            if data:
                return data
        except Exception as e:
            logger.warning("pyttsx3 fallback falhou: %s", e)

        # Último fallback: retorna bytes vazios mas raise fail-closed (não fake mp3)
        raise RuntimeError("TTS indisponivel: nenhum provider conseguiu sintetizar")

_TTS_SINGLETON: Optional[TTSEngine] = None

def get_tts_engine() -> TTSEngine:
    global _TTS_SINGLETON
    if _TTS_SINGLETON is None:
        _TTS_SINGLETON = TTSEngine()
    return _TTS_SINGLETON
