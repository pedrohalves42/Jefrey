"""P5 â€” STT Engine (Speech-to-Text).

Suporta múltiplos providers: Whisper (local), Google Cloud Speech, Azure Speech.
Fail-closed: se provider falha, erro explicativo (nunca mock silencioso).
"""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class STTEngine(ABC):
    """Interface base para engines de STT."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @property
    @abstractmethod
    def language(self) -> str:
        pass

    @abstractmethod
    def transcribe(self, audio_bytes: bytes) -> str:
        """Transcreve Ã¡udio para texto."""
        pass


class WhisperSTTEngine(STTEngine):
    """Whisper local (faster-whisper ou openai-whisper)."""

    def __init__(self, model: str = "base", language: str = "pt", device: str = "cpu"):
        self._model_name = model
        self._language = language
        self._device = device
        self._model = None
        self._load_model()

    def _load_model(self):
        try:
            # Prefer faster-whisper (CTranslate2) for performance
            try:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(self._model_name, device=self._device, compute_type="int8")
                logger.info("WhisperSTT: loaded faster-whisper model=%s device=%s", self._model_name, self._device)
            except ImportError:
                import whisper
                self._model = whisper.load_model(self._model_name, device=self._device)
                logger.info("WhisperSTT: loaded openai-whisper model=%s device=%s", self._model_name, self._device)
        except Exception as e:
            logger.error("WhisperSTT: failed to load model: %s", e)
            raise RuntimeError(f"Failed to load Whisper model '{self._model_name}': {e}")

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def language(self) -> str:
        return self._language

    def transcribe(self, audio_bytes: bytes) -> str:
        if not audio_bytes:
            raise ValueError("Audio data is empty")

        # Write to temp file for whisper
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            if hasattr(self._model, "transcribe"):  # faster-whisper
                segments, info = self._model.transcribe(tmp_path, language=self._language, beam_size=3, vad_filter=True)
                text = " ".join(seg.text for seg in segments).strip()
            else:  # openai-whisper
                result = self._model.transcribe(tmp_path, language=self._language)
                text = result.get("text", "").strip()

            if not text:
                raise ValueError("Transcription returned empty text")
            return text
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


class GoogleSTTEngine(STTEngine):
    """Google Cloud Speech-to-Text (requires credentials)."""

    def __init__(self, language: str = "pt-BR", credentials_path: Optional[str] = None):
        self._language = language
        self._credentials_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self._client = None
        self._init_client()

    def _init_client(self):
        try:
            from google.cloud import speech
            if self._credentials_path and os.path.exists(self._credentials_path):
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self._credentials_path
            self._client = speech.SpeechClient()
            logger.info("GoogleSTT: client initialized")
        except ImportError:
            raise RuntimeError("google-cloud-speech not installed. Run: pip install google-cloud-speech")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Google Speech client: {e}")

    @property
    def model_name(self) -> str:
        return "google-cloud-speech"

    @property
    def language(self) -> str:
        return self._language

    def transcribe(self, audio_bytes: bytes) -> str:
        if not audio_bytes:
            raise ValueError("Audio data is empty")

        from google.cloud import speech

        audio = speech.RecognitionAudio(content=audio_bytes)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            language_code=self._language,
            enable_automatic_punctuation=True,
        )

        response = self._client.recognize(config=config, audio=audio)
        if not response.results:
            raise ValueError("No transcription results from Google")

        transcript = " ".join(r.alternatives[0].transcript for r in response.results)
        return transcript.strip()


class AzureSTTEngine(STTEngine):
    """Azure Speech Service (requires subscription)."""

    def __init__(self, language: str = "pt-BR", region: Optional[str] = None, key: Optional[str] = None):
        self._language = language
        self._region = region or os.getenv("AZURE_SPEECH_REGION")
        self._key = key or os.getenv("AZURE_SPEECH_KEY")
        self._speech_config = None
        self._init_config()

    def _init_config(self):
        try:
            import azure.cognitiveservices.speech as speechsdk
            if not self._key or not self._region:
                raise ValueError("AZURE_SPEECH_KEY and AZURE_SPEECH_REGION required")
            self._speech_config = speechsdk.SpeechConfig(subscription=self._key, region=self._region)
            self._speech_config.speech_recognition_language = self._language
            logger.info("AzureSTT: config initialized region=%s", self._region)
        except ImportError:
            raise RuntimeError("azure-cognitiveservices-speech not installed. Run: pip install azure-cognitiveservices-speech")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Azure Speech config: {e}")

    @property
    def model_name(self) -> str:
        return "azure-speech"

    @property
    def language(self) -> str:
        return self._language

    def transcribe(self, audio_bytes: bytes) -> str:
        if not audio_bytes:
            raise ValueError("Audio data is empty")

        import azure.cognitiveservices.speech as speechsdk
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            audio_config = speechsdk.AudioConfig(filename=tmp_path)
            recognizer = speechsdk.SpeechRecognizer(speech_config=self._speech_config, audio_config=audio_config)
            result = recognizer.recognize_once_async().get()

            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                return result.text.strip()
            elif result.reason == speechsdk.ResultReason.NoMatch:
                raise ValueError("No speech could be recognized")
            else:
                raise RuntimeError(f"Azure STT failed: {result.reason} - {result.error_details}")
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# Singleton factory
_stt_engine: Optional[STTEngine] = None


def get_stt_engine() -> STTEngine:
    """Retorna engine STT configurada (singleton)."""
    global _stt_engine
    if _stt_engine is not None:
        return _stt_engine

    from src.jefrey.core.config import get_settings
    cfg = get_settings()

    provider = getattr(cfg.voice.stt, "provider", "whisper")
    model = getattr(cfg.voice.stt, "model", "base")
    language = getattr(cfg.voice.stt, "language", "pt")
    if provider == "whisper":
        from src.jefrey.core.voice_ready import pick_model
        model = pick_model(model)

    if provider == "whisper":
        _stt_engine = WhisperSTTEngine(model=model, language=language)
    elif provider == "google":
        _stt_engine = GoogleSTTEngine(language=language)
    elif provider == "azure":
        _stt_engine = AzureSTTEngine(language=language)
    else:
        raise ValueError(f"Unknown STT provider: {provider}")

    logger.info("STT engine initialized: provider=%s model=%s", provider, model)
    return _stt_engine


def reset_stt_engine() -> None:
    """Reseta engine (para testes)."""
    global _stt_engine
    _stt_engine = None