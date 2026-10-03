"""P5 â€” TTS Engine (Text-to-Speech).

Suporta múltiplos providers: Piper (local), ElevenLabs, pyttsx3 (fallback).
Fail-closed: se provider falha, erro explicativo (nunca mock silencioso).
"""
from __future__ import annotations

import logging
import os
import tempfile
import subprocess
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class TTSEngine(ABC):
    """Interface base para engines de TTS."""

    @abstractmethod
    def synthesize(self, text: str, voice_id: Optional[str] = None) -> bytes:
        """Sintetiza texto para Ã¡udio (bytes WAV/MP3)."""
        pass


class PiperTTSEngine(TTSEngine):
    """Piper TTS (local, fast, multi-language)."""

    def __init__(self, voice: str = "pt_BR-faber-medium"):
        self._voice = voice
        self._model_path = self._find_model(voice)
        self._check_piper()

    def _find_model(self, voice: str) -> str:
        # Look for model in standard locations
        base_dirs = [
            "/usr/share/piper-voices",
            os.path.expanduser("~/.local/share/piper-voices"),
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "voices"),  # project voices/
        ]
        for base in base_dirs:
            for ext in [".onnx", ".onnx.json"]:
                path = os.path.join(base, voice + ext)
                if os.path.exists(path):
                    return path.replace(".onnx.json", ".onnx")
        # Try direct path
        if os.path.exists(voice):
            return voice
        # Default fallback
        return voice

    def _check_piper(self):
        try:
            result = subprocess.run(["piper", "--help"], capture_output=True, timeout=5)
            if result.returncode != 0:
                raise RuntimeError("piper binary not working")
        except FileNotFoundError:
            raise RuntimeError("piper not installed. Run: pip install piper-tts or install system package")
        except Exception as e:
            raise RuntimeError(f"piper check failed: {e}")

    def synthesize(self, text: str, voice_id: Optional[str] = None) -> bytes:
        if not text or not text.strip():
            raise ValueError("Text is empty")

        voice = voice_id or self._voice
        model_path = self._find_model(voice)

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Piper model not found: {model_path}")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            output_path = tmp.name

        try:
            cmd = [
                "piper",
                "--model", model_path,
                "--output_file", output_path,
            ]
            # Add config if exists
            config_path = model_path + ".json"
            if os.path.exists(config_path):
                cmd.extend(["--config", config_path])

            proc = subprocess.run(cmd, input=text.encode("utf-8"), capture_output=True, timeout=30)
            if proc.returncode != 0:
                raise RuntimeError(f"piper failed: {proc.stderr.decode('utf-8', errors='ignore')}")

            with open(output_path, "rb") as f:
                audio_bytes = f.read()

            if not audio_bytes or audio_bytes[:4] != b"RIFF":
                raise RuntimeError("piper produced invalid WAV output")

            return audio_bytes
        finally:
            try:
                os.unlink(output_path)
            except Exception:
                pass


class ElevenLabsTTSEngine(TTSEngine):
    """ElevenLabs TTS (cloud, high quality, requires API key)."""

    def __init__(self, api_key: Optional[str] = None, default_voice: str = "Charon"):
        self._api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self._default_voice = default_voice
        if not self._api_key:
            raise ValueError("ELEVENLABS_API_KEY required for ElevenLabs TTS")

    def synthesize(self, text: str, voice_id: Optional[str] = None) -> bytes:
        if not text or not text.strip():
            raise ValueError("Text is empty")

        import httpx

        voice = voice_id or self._default_voice
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self._api_key,
        }

        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code != 200:
                    raise RuntimeError(f"ElevenLabs API error: {resp.status_code} - {resp.text}")
                return resp.content
        except httpx.RequestError as e:
            raise RuntimeError(f"ElevenLabs request failed: {e}")


class Pyttsx3TTSEngine(TTSEngine):
    """pyttsx3 fallback (system TTS, no internet required)."""

    def __init__(self, voice: Optional[str] = None, rate: int = 150):
        self._voice = voice
        self._rate = rate
        self._engine = None
        self._init_engine()

    def _init_engine(self):
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self._rate)
            if self._voice:
                voices = self._engine.getProperty("voices")
                for v in voices:
                    if self._voice.lower() in v.name.lower() or self._voice.lower() in v.id.lower():
                        self._engine.setProperty("voice", v.id)
                        break
            logger.info("pyttsx3 engine initialized")
        except ImportError:
            raise RuntimeError("pyttsx3 not installed. Run: pip install pyttsx3")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize pyttsx3: {e}")

    def synthesize(self, text: str, voice_id: Optional[str] = None) -> bytes:
        if not text or not text.strip():
            raise ValueError("Text is empty")

        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            output_path = tmp.name

        try:
            self._engine.save_to_file(text, output_path)
            self._engine.runAndWait()

            with open(output_path, "rb") as f:
                audio_bytes = f.read()

            if not audio_bytes:
                raise RuntimeError("pyttsx3 produced empty output")

            return audio_bytes
        finally:
            try:
                os.unlink(output_path)
            except Exception:
                pass


# Singleton factory
_tts_engine: Optional[TTSEngine] = None


def get_tts_engine() -> TTSEngine:
    """Retorna engine TTS configurada (singleton)."""
    global _tts_engine
    if _tts_engine is not None:
        return _tts_engine

    from src.jefrey.core.config import get_settings
    cfg = get_settings()

    provider = getattr(cfg.voice.tts, "provider", "piper")
    voice = getattr(cfg.voice.tts, "voice", "pt_BR-faber-medium")

    if provider == "piper":
        _tts_engine = PiperTTSEngine(voice=voice)
    elif provider == "elevenlabs":
        _tts_engine = ElevenLabsTTSEngine(default_voice=voice)
    elif provider == "pyttsx3":
        _tts_engine = Pyttsx3TTSEngine(voice=voice)
    else:
        raise ValueError(f"Unknown TTS provider: {provider}")

    logger.info("TTS engine initialized: provider=%s voice=%s", provider, voice)
    return _tts_engine


def reset_tts_engine() -> None:
    """Reseta engine (para testes)."""
    global _tts_engine
    _tts_engine = None