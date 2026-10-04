"""Modo nativo (sem Docker): configura tudo sozinho e sobe o Jefrey para uma pessoa comum.

  - dados em %LOCALAPPDATA%\\Jefrey (config, banco SQLite, memorias, arquivos): nada de .env;
  - chave secreta gerada na primeira vez e guardada ali;
  - aceita conexoes SO deste computador (127.0.0.1);
  - garante o Ollama (programa que roda os modelos locais) e baixa os modelos que faltam;
  - abre o navegador quando estiver pronto.
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import re
import socket
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
    """Baixa os modelos que faltam (a tela mostra 'baixando...'). Implementacao unica em core/model_pull."""
    from src.jefrey.core import model_pull

    os.environ.setdefault("JEFREY_CONFIG_DIR", str(progress_file.parent))
    model_pull._run(models, OLLAMA_URL)


# ---------------------------------------------------------------- registros, porta e bandeja
_REDACT = [
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}"), r"\1***"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"), "sk-***"),
    (re.compile(r"(?i)((?:api[_-]?key|token|secret|password|senha)[\"'=: ]+)[^\s\"',}]{6,}"), r"\1***"),
]


def redact(text: str) -> str:
    for rx, rep in _REDACT:
        text = rx.sub(rep, text)
    return text


class _RedactFilter(logging.Filter):
    """Nenhuma chave ou token chega ao arquivo de registros, mesmo que algum modulo registre sem querer."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact(record.getMessage())
            record.args = ()
        except Exception:
            pass
        return True


def setup_logging(logs_dir: Path) -> Path:
    """Registros em arquivo com rodizio (3 x 1 MB). Sem console no programa instalado, e o que o suporte le."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / "jefrey.log"
    handler = logging.handlers.RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(_RedactFilter())
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = [handler]
        lg.propagate = False
        lg.setLevel(logging.INFO)
    return path


def ensure_std_streams() -> None:
    """Programa sem console (janela oculta): stdout/stderr vem como None e quebraria print e logging."""
    for name in ("stdout", "stderr"):
        if getattr(sys, name, None) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))


def port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1) if hasattr(socket, "SO_EXCLUSIVEADDRUSE") else None
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def find_free_port(start: int = DEFAULT_PORT, tries: int = 20) -> int:
    """Primeira porta livre a partir de `start` (outro programa pode estar usando a 8000)."""
    for p in range(start, start + tries):
        if port_free(p):
            return p
    raise OSError(f"nenhuma porta livre entre {start} e {start + tries - 1}")


def start_tray(url: str, logs_dir: Path, on_quit) -> "object | None":
    """Icone na bandeja com Abrir / Ver registros / Sair. Sem pystray ou sem bandeja, segue sem (nunca derruba)."""
    try:
        import pystray
        from PIL import Image
    except Exception:
        return None
    icon_path = Path(__file__).resolve().parents[1] / "static" / "images" / "icon-192.png"
    try:
        image = Image.open(icon_path) if icon_path.is_file() else Image.new("RGB", (64, 64), (6, 182, 212))

        def open_app(_icon=None, _item=None):
            webbrowser.open(url)

        def open_logs(_icon=None, _item=None):
            try:
                os.startfile(str(logs_dir))  # type: ignore[attr-defined]
            except Exception:
                pass

        def quit_(icon=None, _item=None):
            on_quit()

        menu = pystray.Menu(
            pystray.MenuItem("Abrir o Jefrey", open_app, default=True),
            pystray.MenuItem("Ver registros (para suporte)", open_logs),
            pystray.MenuItem("Sair", quit_),
        )
        icon = pystray.Icon("Jefrey", image, "Jefrey", menu)
        icon.run_detached()
        try:  # avisos do Windows (lembretes, resumo da manha): balao perto do relogio
            from src.jefrey.core import notify

            notify.set_sink(lambda title, text: icon.notify(text, title))
        except Exception:
            pass
        return icon
    except Exception:
        return None


def tray_title(snapshot: dict) -> str:
    """Texto do icone da bandeja (aparece ao parar o mouse em cima)."""
    if snapshot.get("studying"):
        return "Jefrey: estudando" + (f" {snapshot['topic']}" if snapshot.get("topic") else "")
    if snapshot.get("learning"):
        return "Jefrey: aprendendo com a conversa"
    return "Jefrey"


def start_tray_updates(icon, interval_s: float = 5.0) -> threading.Event:
    """Atualiza o texto do icone com o que o Jefrey esta fazendo. Devolve o evento que para a atualizacao."""
    stop = threading.Event()

    def loop() -> None:
        from src.jefrey.core import activity

        last = ""
        while not stop.wait(interval_s):
            try:
                title = tray_title(activity.any_busy())
                if title != last:
                    icon.title = title[:120]
                    last = title
            except Exception:
                pass

    threading.Thread(target=loop, daemon=True, name="jefrey-tray-title").start()
    return stop


def start_global_hotkey(url: str, no_browser: bool):
    """Atalho global (Ctrl+Alt+J): traz o Jefrey para a frente (ou abre) e manda ele comecar a ouvir."""
    if os.getenv("JEFREY_NO_HOTKEY"):
        return None
    try:
        from src.jefrey.core import wake
        from src.jefrey.native import hotkey

        def on_press() -> None:
            wake.request()
            if wake.ui_alive():
                hotkey.focus_window()
            elif not no_browser:
                webbrowser.open(url)  # a tela nova pergunta pelo pedido ao abrir

        return hotkey.start_hotkey(on_press)
    except Exception:
        return None


def local_model_chosen() -> bool:
    """So baixa modelo local se a pessoa escolheu o modo local (nuvem e o padrao recomendado)."""
    try:
        from src.jefrey.core.llm_provider import load_override
        return (load_override().get("provider") or "") == "ollama"
    except Exception:
        return False


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
    ensure_std_streams()
    args = argv if argv is not None else sys.argv[1:]
    no_browser = "--no-browser" in args or bool(os.getenv("JEFREY_NO_BROWSER"))
    no_tray = "--no-tray" in args or bool(os.getenv("JEFREY_NO_TRAY"))
    desired = int(os.getenv("JEFREY_API_PORT", str(DEFAULT_PORT)))
    if jefrey_running(desired):
        url = f"http://127.0.0.1:{desired}"
        print(f"O Jefrey ja esta aberto em {url}")
        if not no_browser:
            webbrowser.open(url)
        return 0
    try:
        port = find_free_port(desired)  # outro programa pode estar usando a porta
    except OSError as e:
        print(f"[erro] {e}")
        return 1
    url = f"http://127.0.0.1:{port}"

    home = Path(os.getenv("JEFREY_HOME") or default_home())
    env = build_env(home, port=port)
    os.environ.update(env)
    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    os.chdir(home)  # caminhos relativos antigos ("data/...") caem dentro da pasta do usuario
    import src.jefrey.core.logging  # noqa: F401,E402  (zera os handlers do logger raiz ao ser importado: tem que vir ANTES do arquivo)

    logs_dir = home / "logs"
    log_path = setup_logging(logs_dir)
    logging.getLogger("jefrey.launcher").info("iniciando na porta %s (registros em %s)", port, log_path)

    if local_model_chosen():  # nuvem e o padrao: so prepara modelo local se a pessoa escolheu local
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

    import uvicorn

    from src.jefrey.native import control

    server = uvicorn.Server(uvicorn.Config("src.jefrey.api.main:app", host="127.0.0.1", port=port, log_config=None, reload=False))

    def quit_now() -> None:
        logging.getLogger("jefrey.launcher").info("pedido para sair")
        server.should_exit = True

    control.set_quit_hook(quit_now)
    tray = None if no_tray else start_tray(url, logs_dir, quit_now)
    tray_updates = start_tray_updates(tray) if tray is not None else None
    stop_hotkey = start_global_hotkey(url, no_browser)
    try:
        server.run()
    finally:
        if stop_hotkey is not None:
            stop_hotkey()
        if tray_updates is not None:
            tray_updates.set()
        control.set_quit_hook(None)
        if tray is not None:
            try:
                tray.stop()
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
