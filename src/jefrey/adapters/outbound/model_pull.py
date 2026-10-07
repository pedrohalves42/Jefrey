"""Baixar modelos locais pelo Ollama, com progresso para a tela (usado quando a pessoa escolhe o modo local)."""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/\-]{0,79}$")
MAX_MODELS = 3
_lock = threading.Lock()
_running = False


class PullError(RuntimeError):
    """Mensagem segura para mostrar a pessoa."""


def progress_file() -> Path:
    return Path(os.getenv("JEFREY_CONFIG_DIR", "config")) / "models_progress.json"


def ollama_url() -> str:
    return (os.getenv("JEFREY_LLM__BASE_URL") or "http://127.0.0.1:11434").rstrip("/")


def valid_models(models: list[str]) -> list[str]:
    clean = [m.strip() for m in models if isinstance(m, str) and m.strip()]
    if not clean or len(clean) > MAX_MODELS or any(not _NAME.match(m) for m in clean):
        raise PullError("Nome de modelo invalido.")
    return list(dict.fromkeys(clean))


def _save(state: dict) -> None:
    f = progress_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    os.replace(tmp, f)


def status() -> dict:
    try:
        d = json.loads(progress_file().read_text(encoding="utf-8"))
        if isinstance(d, dict):
            return {"running": _running, "done": bool(d.get("done")), "models": d.get("models", {}), "error": d.get("error")}
    except (OSError, ValueError):
        pass
    return {"running": _running, "done": False, "models": {}, "error": None}


def _run(models: list[str], base: str, transport: Optional[httpx.BaseTransport] = None) -> None:
    global _running
    state: dict = {"models": {m: {"status": "esperando", "percent": 0} for m in models}, "done": False, "error": None}
    _save(state)
    try:
        for m in models:
            try:
                with httpx.Client(timeout=httpx.Timeout(None, connect=10.0), transport=transport) as c:
                    with c.stream("POST", base + "/api/pull", json={"name": m, "stream": True}) as r:
                        r.raise_for_status()
                        for line in r.iter_lines():
                            if not line:
                                continue
                            ev = json.loads(line)
                            total, done = ev.get("total") or 0, ev.get("completed") or 0
                            if ev.get("error"):
                                raise PullError(str(ev["error"])[:120])
                            state["models"][m] = {"status": str(ev.get("status", ""))[:60],
                                                  "percent": int(done * 100 / total) if total else state["models"][m]["percent"]}
                            _save(state)
                state["models"][m] = {"status": "pronto", "percent": 100}
            except Exception as e:
                logger.warning("download de %s falhou: %s", m, type(e).__name__)
                state["models"][m] = {"status": "falhou", "percent": state["models"][m]["percent"]}
                state["error"] = f"Nao consegui baixar {m}. Verifique a internet e o espaco em disco."
            _save(state)
    finally:
        state["done"] = True
        _save(state)
        with _lock:
            _running = False


def start(models: list[str], ensure_running=None) -> dict:
    """Inicia o download em segundo plano. Levanta PullError com mensagem clara se nao der para comecar."""
    global _running
    models = valid_models(models)
    if ensure_running is None:
        from src.jefrey.native.launcher import ensure_ollama as ensure_running  # noqa: N813
    ok, msg = ensure_running()
    if not ok:
        raise PullError(msg)
    with _lock:
        if _running:
            return status()  # ja esta baixando: nao duplica
        _running = True
    threading.Thread(target=_run, args=(models, ollama_url()), daemon=True).start()
    return {"running": True, "done": False, "models": {m: {"status": "esperando", "percent": 0} for m in models}, "error": None}
