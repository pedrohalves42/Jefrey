"""P1.1 — STT Engine (Axiom #1 FAIL-CLOSED, #3 SEM STUB, HPP cap1-4, Building LLM Apps fallback)."""
from __future__ import annotations
import io
import logging
import tempfile
import os
from typing import Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

# Axiom #3: mock só em dev
def _is_mock_enabled() -> bool:
    try:
        from src.jefrey.core.config import get_settings
        cfg = get_settings()
        return bool(cfg.debug) and os.getenv("JEFREY_STT__MOCK", "false").lower() in ("1","true","yes")
    except Exception:
        return False

class STTEngine:
    """STT via faster-whisper small int8 pt-BR; fallback mock fail-closed."""
    def __init__(self, model: str = "small", language: str = "pt"):
        self.model_name = model
        self.language = language
        self._model = None
        self._load_error: Optional[str] = None

    def _ensure_model(self):
        if self._model is not None or self._load_error is not None:
            return
        if _is_mock_enabled():
            logger.info("STT mock enabled (dev)")
            return
        try:
            from faster_whisper import WhisperModel
            # HPP cap2: int8 cpu, lazy load
            self._model = WhisperModel(self.model_name, device="cpu", compute_type="int8", download_root="/tmp/hf-cache")
            logger.info("STT model loaded %s", self.model_name)
        except Exception as e:
            self._load_error = str(e)
            logger.warning("STT model load failed: %s", e)

    def transcribe(self, audio_bytes: bytes, language: Optional[str] = None) -> str:
        """Transcribe wav/webm bytes -> text. Fail-closed on error (Axiom #1)."""
        if not audio_bytes or len(audio_bytes) < 100:
            raise ValueError("audio vazio ou muito curto")
        if _is_mock_enabled():
            return "mock transcript: olá jefrey"
        self._ensure_model()
        if self._model is None:
            # Building LLM Apps fallback: não inventa transcript, raise fail-closed
            if self._load_error:
                raise RuntimeError(f"STT indisponivel: {self._load_error}")
            raise RuntimeError("STT modelo nao carregado")
        # HPP cap1: write temp file for faster-whisper (prefere path)
        lang = language or self.language
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            segments, info = self._model.transcribe(tmp_path, language=lang, beam_size=5)
            text = " ".join(s.text.strip() for s in segments).strip()
            if not text:
                raise RuntimeError("transcricao vazia")
            return text
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

# Singleton com WeakValueDictionary cache pattern (HPP)
_STT_SINGLETON: Optional[STTEngine] = None

def get_stt_engine() -> STTEngine:
    global _STT_SINGLETON
    if _STT_SINGLETON is None:
        try:
            from src.jefrey.core.config import get_settings
            cfg = get_settings()
            model = getattr(cfg.voice.stt, "model", "small") or "small"
            lang = getattr(cfg.voice.stt, "language", "pt") or "pt"
        except Exception:
            model, lang = "small", "pt"
        _STT_SINGLETON = STTEngine(model=model, language=lang)
    return _STT_SINGLETON
