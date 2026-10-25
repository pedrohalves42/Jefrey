"""Preparar a audicao do Jefrey (Whisper local).

Na primeira vez o modelo de voz precisa ser baixado (centenas de MB). Isso nao pode acontecer escondido, dentro do
primeiro pedido de voz: a pessoa acharia que travou. Aqui o download roda em segundo plano e a tela mostra o andamento.
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_state: dict = {"running": False, "error": None}

FRIENDLY_ERROR = "Não consegui preparar a minha audição. Verifique a internet e tente de novo."


def pick_model(configured: str) -> str:
    """Modelo de voz: o configurado; se ninguem configurou, o melhor que o computador aguenta."""
    if os.getenv("JEFREY_VOICE__STT__MODEL"):
        return configured
    cores = os.cpu_count() or 2
    return "small" if cores >= 6 else "base"


def _hub_cache() -> Path:
    try:
        from huggingface_hub import constants

        return Path(constants.HF_HUB_CACHE)
    except Exception:
        return Path(os.getenv("HF_HOME", str(Path.home() / ".cache" / "huggingface"))) / "hub"


def model_cached(name: str) -> bool:
    """O modelo ja esta no computador (nao precisa baixar)?"""
    repo = _hub_cache() / f"models--Systran--faster-whisper-{name}" / "snapshots"
    try:
        return any((snap / "model.bin").exists() for snap in repo.iterdir())
    except OSError:
        return False


def _configured_model() -> str:
    try:
        from src.jefrey.core.config import get_settings

        return pick_model(getattr(get_settings().voice.stt, "model", "base"))
    except Exception:
        return pick_model("base")


def _engine_loaded() -> bool:
    try:
        from src.jefrey.core import stt_engine

        return stt_engine._stt_engine is not None
    except Exception:
        return False


def status() -> dict:
    model = _configured_model()
    ready = _engine_loaded() or model_cached(model)
    return {"ready": ready, "running": bool(_state["running"]), "error": _state["error"], "model": model}


def _default_loader() -> None:
    from src.jefrey.core.stt_engine import get_stt_engine

    get_stt_engine()


def _run(loader: Callable[[], None]) -> None:
    try:
        loader()
        _state["error"] = None
    except Exception as e:  # mensagem tecnica so no registro, nunca na tela
        logger.warning("preparar audicao falhou: %s", type(e).__name__)
        _state["error"] = FRIENDLY_ERROR
    finally:
        _state["running"] = False


def prepare(loader: Optional[Callable[[], None]] = None) -> bool:
    """Comeca a preparar em segundo plano. False se ja estava preparando."""
    with _lock:
        if _state["running"]:
            return False
        _state["running"] = True
        _state["error"] = None
    threading.Thread(target=_run, args=(loader or _default_loader,), daemon=True, name="voice-prepare").start()
    return True
