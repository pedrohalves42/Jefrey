"""Modo nativo (sem Docker): configura tudo sozinho e sobe o Jefrey para uma pessoa comum.

  - dados em %LOCALAPPDATA%\\Jefrey (config, banco SQLite, memorias, arquivos): nada de .env;
  - chave secreta gerada na primeira vez e guardada ali;
  - aceita conexoes SO deste computador (127.0.0.1);
  - garante o Ollama (programa que roda os modelos locais) e baixa os modelos que faltam;
  - abre o navegador quando estiver pronto.
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Mapping, Optional

import httpx

DEFAULT_PORT = 8000
OLLAMA_URL = "http://127.0.0.1:11434"
REQUIRED_MODELS = ("qwen3:1.7b", "embeddinggemma")


def default_home() -> Path:
    base = os.getenv("LOCALAPPDATA") or os.getenv("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "Jefrey"


def ensure_secrets(config_dir: Path) -> dict[str, str]:
    """Gera (uma vez) e le as chaves internas. Arquivo so do usuario; nunca vai para o navegador."""
    config_dir.mkdir(parents=True, exist_ok=True)
    f = config_dir / "native_secrets.json"
    data: dict = {}
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    changed = False
    for k in ("api_secret", "hmac_key"):
        if not isinstance(data.get(k), str) or len(data[k]) < 32:
            data[k] = secrets.token_hex(32)
            changed = True
    if changed:
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, f)
        try:
            os.chmod(f, 0o600)
        except OSError:
            pass
    return {"api_secret": data["api_secret"], "hmac_key": data["hmac_key"]}


def build_env(home: Path, base: Optional[Mapping[str, str]] = None, port: int = DEFAULT_PORT) -> dict[str, str]:
    """Variaveis de ambiente do modo nativo. O que o usuario ja definiu tem prioridade (exceto o modo)."""
    base = dict(base if base is not None else os.environ)
    sec = ensure_secrets(home / "config")
    data = home / "data"
    for d in (data, data / "files", data / "chroma_db", home / "config"):
        d.mkdir(parents=True, exist_ok=True)
    db = (data / "jefrey.db").as_posix()
    defaults = {
        "JEFREY_ENV": "dev",  # a tela entra com sessao local; seguro porque so ouve em 127.0.0.1
        "JEFREY_DEBUG": "false",
        "JEFREY_API__SECRET_KEY": sec["api_secret"],
        "JEFREY_EVENTBUS__HMAC_KEY": sec["hmac_key"],
        "JEFREY_DATABASE__URL": f"sqlite:///{db}",
        "JEFREY_LLM__BASE_URL": OLLAMA_URL,
        "JEFREY_EMBEDDINGS__BASE_URL": OLLAMA_URL,
        "JEFREY_REDIS__HOST": "127.0.0.1",
        "JEFREY_CONFIG_DIR": str(home / "config"),
        "JEFREY_FILES_DIR": str(data / "files"),
        "JEFREY_MEMORY__LONG_TERM__PERSIST_DIRECTORY": str(data / "chroma_db"),
        "JEFREY_API__AUDIT_FALLBACK_PATH": str(data / "audit_fallback.jsonl"),
        "JEFREY_API_PORT": str(port),
        "ANONYMIZED_TELEMETRY": "False",
    }
    env = {**defaults, **{k: v for k, v in base.items() if k in defaults and v}}
    env["JEFREY_MODE"] = "native"
    env["JEFREY_API_HOST"] = "127.0.0.1"  # nunca exposto na rede, aconteca o que acontecer
    return env


# ---------------------------------------------------------------- Ollama
def find_ollama() -> Optional[Path]:
    found = shutil.which("ollama")
    if found:
        return Path(found)
    for cand in (Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
                 Path(os.getenv("ProgramFiles", "")) / "Ollama" / "ollama.exe"):
        if cand.is_file():
            return cand
    return None


def ollama_up(url: str = OLLAMA_URL, timeout: float = 2.0) -> bool:
    try:
        return httpx.get(url + "/api/version", timeout=timeout).status_code == 200
    except httpx.HTTPError:
        return False


def ensure_ollama(wait: float = 25.0) -> tuple[bool, str]:
    """(ok, mensagem para a pessoa). Inicia o Ollama se estiver instalado e parado."""
    if ollama_up():
        return True, "Ollama ja estava rodando"
    exe = find_ollama()
    if exe is None:
        return False, "O Ollama (que roda os modelos de IA no seu computador) nao esta instalado. Baixe em ollama.com/download."
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen([str(exe), "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    end = time.time() + wait
    while time.time() < end:
        if ollama_up():
            return True, "Ollama iniciado"
        time.sleep(0.5)
    return False, "O Ollama nao respondeu a tempo."


def missing_models(have: list[str], wanted: tuple[str, ...] = REQUIRED_MODELS) -> list[str]:
    def ok(w: str) -> bool:
        return any(h == w or (":" not in w and h.split(":")[0] == w) for h in have)
    return [w for w in wanted if not ok(w)]


def installed_models() -> list[str]:
    try:
        r = httpx.get(OLLAMA_URL + "/api/tags", timeout=5)
        return [m.get("name", "") for m in r.json().get("models", [])]
    except (httpx.HTTPError, ValueError):
        return []


def pull_models(progress_file: Path, models: list[str]) -> None:
    """Baixa os modelos que faltam gravando o progresso (a tela mostra 'baixando...')."""
    state = {"models": {m: {"status": "esperando", "percent": 0} for m in models}, "done": False}

    def save():
        progress_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = progress_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(state), encoding="utf-8")
        os.replace(tmp, progress_file)

    save()
    for m in models:
        try:
            with httpx.stream("POST", OLLAMA_URL + "/api/pull", json={"name": m, "stream": True}, timeout=None) as r:
                for line in r.iter_lines():
                    if not line:
                        continue
                    ev = json.loads(line)
                    total, done = ev.get("total") or 0, ev.get("completed") or 0
                    state["models"][m] = {"status": ev.get("status", ""), "percent": int(done * 100 / total) if total else state["models"][m]["percent"]}
                    save()
            state["models"][m] = {"status": "pronto", "percent": 100}
        except Exception as e:
            state["models"][m] = {"status": f"falhou: {type(e).__name__}", "percent": 0}
        save()
    state["done"] = True
    save()


# ---------------------------------------------------------------- execucao
def jefrey_running(port: int) -> bool:
    try:
        r = httpx.get(f"http://127.0.0.1:{port}/health", timeout=2)
        return r.status_code == 200 and "security_components" in r.text
    except httpx.HTTPError:
        return False


def wait_ready(port: int, timeout: float = 120.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if jefrey_running(port):
            return True
        time.sleep(0.5)
    return False


def main(argv: Optional[list[str]] = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    no_browser = "--no-browser" in args or bool(os.getenv("JEFREY_NO_BROWSER"))
    port = int(os.getenv("JEFREY_API_PORT", str(DEFAULT_PORT)))
    url = f"http://127.0.0.1:{port}"
    if jefrey_running(port):
        print(f"O Jefrey ja esta aberto em {url}")
        if not no_browser:
            webbrowser.open(url)
        return 0

    home = Path(os.getenv("JEFREY_HOME") or default_home())
    env = build_env(home, port=port)
    os.environ.update(env)
    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    os.chdir(home)  # caminhos relativos antigos ("data/...") caem dentro da pasta do usuario

    ok, msg = ensure_ollama()
    print(("[ok] " if ok else "[aviso] ") + msg)
    if ok:
        need = missing_models(installed_models())
        if need:
            print("Baixando modelos que faltam (so na primeira vez):", ", ".join(need))
            threading.Thread(target=pull_models, args=(home / "data" / "models_progress.json", need), daemon=True).start()

    def open_when_ready():
        if wait_ready(port) and not no_browser:
            webbrowser.open(url)

    threading.Thread(target=open_when_ready, daemon=True).start()
    from src.jefrey.api.main import main as run_server
    run_server()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
