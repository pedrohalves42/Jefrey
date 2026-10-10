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

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8000
OLLAMA_URL = "http://127.0.0.1:11434"
REQUIRED_MODELS = ("qwen3:1.7b", "embeddinggemma")


def default_home() -> Path:
    base = os.getenv("LOCALAPPDATA") or os.getenv("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "Jefrey"


SEED_FILES = ("google_oauth.json", "update_url.txt", "update_public_key.txt")


def defaults_dir() -> Optional[Path]:
    """Pasta `defaults` que acompanha o instalador (credenciais do app Google, endereco e chave das atualizacoes)."""
    cands = []
    if getattr(sys, "frozen", False):
        cands.append(Path(sys.executable).resolve().parent / "defaults")
    cands.append(Path(__file__).resolve().parents[3] / "packaging" / "defaults")
    return next((c for c in cands if c.is_dir()), None)


def seed_defaults(config_dir: Path, source: Optional[Path] = None) -> list[str]:
    """Na primeira abertura copia os padroes do instalador para a pasta de dados. Nunca sobrescreve o que a pessoa ja tem."""
    src = source if source is not None else defaults_dir()
    copied: list[str] = []
    if src is None:
        return copied
    config_dir.mkdir(parents=True, exist_ok=True)
    for name in SEED_FILES:
        s, d = src / name, config_dir / name
        try:
            if s.is_file() and not d.exists() and s.stat().st_size < 20_000:
                d.write_bytes(s.read_bytes())
                copied.append(name)
        except OSError:
            continue
    return copied


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
        except OSError as _e:
            logger.debug("ignorado (launcher): %s", type(_e).__name__)
    return {"api_secret": data["api_secret"], "hmac_key": data["hmac_key"]}


def build_env(home: Path, base: Optional[Mapping[str, str]] = None, port: int = DEFAULT_PORT) -> dict[str, str]:
    """Variaveis de ambiente do modo nativo. O que o usuario ja definiu tem prioridade (exceto o modo)."""
    base = dict(base if base is not None else os.environ)
    sec = ensure_secrets(home / "config")
    seed_defaults(home / "config")
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
        except Exception as _e:
            logger.debug("ignorado (launcher): %s", type(_e).__name__)
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


def start_tray(url: str, logs_dir: Path, on_quit, on_open=None, on_orb=None, on_restart=None, on_messages=None) -> "object | None":
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
            if on_open is not None:
                on_open()
            else:
                webbrowser.open(url)

        def restart(_icon=None, _item=None):
            if on_restart is not None:
                on_restart()

        def orb(_icon=None, _item=None):
            if on_orb is not None:
                on_orb()

        def messages(_icon=None, _item=None):
            if on_messages is not None:
                on_messages()

        def open_logs(_icon=None, _item=None):
            try:
                os.startfile(str(logs_dir))  # type: ignore[attr-defined]
            except Exception as _e:
                logger.debug("ignorado (launcher): %s", type(_e).__name__)

        def quit_(icon=None, _item=None):
            on_quit()

        menu = pystray.Menu(
            pystray.MenuItem("Abrir o Jefrey", open_app, default=True),
            *([pystray.MenuItem("Mensagens (WhatsApp dentro do Jefrey)", messages)] if on_messages is not None else []),
            *([pystray.MenuItem("Mostrar o orbe (bolinha na tela)", orb)] if on_orb is not None else []),
            pystray.MenuItem("Ver registros (para suporte)", open_logs),
            *([pystray.MenuItem("Reiniciar o Jefrey", restart)] if on_restart is not None else []),
            pystray.MenuItem("Sair", quit_),
        )
        icon = pystray.Icon("Jefrey", image, "Jefrey", menu)
        icon.run_detached()
        try:  # avisos do Windows (lembretes, resumo da manha): balao perto do relogio
            from src.jefrey.core import notify

            notify.set_sink(lambda title, text: icon.notify(text, title))
        except Exception as _e:
            logger.debug("ignorado (launcher): %s", type(_e).__name__)
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
            except Exception as _e:
                logger.debug("ignorado (launcher): %s", type(_e).__name__)

    threading.Thread(target=loop, daemon=True, name="jefrey-tray-title").start()
    return stop


HALT_HOTKEY = "ctrl+alt+p"  # "Parar": interrompe qualquer acao do Jefrey no computador, de qualquer janela


def start_halt_hotkey():
    if os.getenv("JEFREY_NO_HOTKEY"):
        return None
    try:
        from src.jefrey.core import halt
        from src.jefrey.native import hotkey

        return hotkey.start_hotkey(halt.request_halt, HALT_HOTKEY)
    except Exception as e:
        logger.info("atalho de parada indisponivel (%s)", type(e).__name__)
        return None


def start_global_hotkey(url: str, no_browser: bool, on_show=None):
    """Atalho global (Ctrl+Alt+J): traz o Jefrey para a frente (ou abre) e manda ele comecar a ouvir."""
    if os.getenv("JEFREY_NO_HOTKEY"):
        return None
    try:
        from src.jefrey.core import wake
        from src.jefrey.native import hotkey

        def on_press() -> None:
            wake.request()
            if on_show is not None:
                on_show()
            elif wake.ui_alive():
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


def native_running(port: int) -> bool:
    """So conta como "ja aberto" a copia NATIVA desta mesma versao. Outra copia (Docker, versao antiga) na mesma porta nao serve:
    antes o programa instalado desistia e abria o Jefrey velho do Docker, sem o Google e as skills novas."""
    try:
        r = httpx.get(f"http://127.0.0.1:{port}/health", timeout=2)
        if r.status_code != 200:
            return False
        d = r.json()
        from src.jefrey import __version__

        return d.get("mode") == "native" and d.get("version") == __version__
    except (httpx.HTTPError, ValueError):
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
    minimized = "--minimized" in args  # iniciado junto com o Windows: fica so na bandeja
    restart = "--restart" in args  # "Reiniciar o Jefrey": fecha a copia aberta (se houver) e abre de novo
    desired = int(os.getenv("JEFREY_API_PORT", str(DEFAULT_PORT)))
    from src.jefrey.native import shell as shell_mod

    home0 = Path(os.getenv("JEFREY_HOME") or default_home())
    if restart and jefrey_running(desired):
        shell_mod.ask_running_to_quit(home0)
        end = time.time() + 30
        while time.time() < end and jefrey_running(desired):
            time.sleep(0.5)
    shell_mod.clear_quit_signal(home0)  # sinal velho nunca fecha a copia nova

    use_window = not no_browser and shell_mod.webview_available()
    if native_running(desired):
        url = f"http://127.0.0.1:{desired}"
        print(f"O Jefrey ja esta aberto em {url}")
        if use_window:
            shell_mod.ask_running_to_show(Path(os.getenv("JEFREY_HOME") or default_home()))  # traz a janela que ja existe
        elif not no_browser:
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

    if not use_window:
        threading.Thread(target=open_when_ready, daemon=True).start()

    import uvicorn

    from src.jefrey.native import control

    server = uvicorn.Server(uvicorn.Config("src.jefrey.api.main:app", host="127.0.0.1", port=port, log_config=None, reload=False))

    def quit_now() -> None:
        logging.getLogger("jefrey.launcher").info("pedido para sair")
        server.should_exit = True

    shell = shell_mod.DesktopShell(url, home, quit_now, start_hidden=minimized) if use_window else None

    def quit_all() -> None:
        quit_now()
        if shell is not None:
            shell.quit()

    def restart_self() -> None:
        """Abre uma copia nova (que espera esta fechar) e fecha esta."""
        try:
            cmd = shell_mod.restart_command(bool(getattr(sys, "frozen", False)), sys.executable)
            flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            subprocess.Popen(cmd, cwd=str(root) if not getattr(sys, "frozen", False) else None, creationflags=flags, close_fds=True)
        except OSError as e:
            logging.getLogger("jefrey.launcher").warning("nao consegui reiniciar (%s)", type(e).__name__)
            return
        quit_all()

    control.set_quit_hook(quit_all)
    control.set_restart_hook(restart_self)
    quit_watch_stop = threading.Event()
    shell_mod.watch_quit_signal(home, quit_all, quit_watch_stop)  # "Reiniciar o Jefrey" de fora pede por arquivo
    if shell is not None:
        control.set_window_hooks(shell.show, shell.show_orb)
        control.set_messages_hook(shell.show_messages)
    tray =None if no_tray else start_tray(url, logs_dir, quit_all, on_open=shell.show if shell else None, on_orb=shell.show_orb if shell else None, on_restart=restart_self,
                     on_messages=(lambda: shell.show_messages()) if shell else None)
    if shell is not None and tray is not None:
        shell.set_tray_notice(lambda title, text: tray.notify(text, title))
    tray_updates = start_tray_updates(tray) if tray is not None else None
    stop_hotkey = start_global_hotkey(url, no_browser, on_show=shell.show if shell else None)
    stop_halt = start_halt_hotkey()
    try:
        if shell is not None:
            server_thread = threading.Thread(target=server.run, daemon=True, name="jefrey-server")
            server_thread.start()
            try:
                shell.run(lambda: wait_ready(port))  # bloqueia ate a pessoa escolher Sair
            except Exception:
                logger.exception("a janela falhou; seguindo pelo navegador")
                if wait_ready(port):
                    webbrowser.open(url)
                    server_thread.join()
            server.should_exit = True
            server_thread.join(timeout=15)
        else:
            server.run()
    finally:
        if stop_hotkey is not None:
            stop_hotkey()
        if stop_halt is not None:
            stop_halt()
        if tray_updates is not None:
            tray_updates.set()
        control.set_quit_hook(None)
        control.set_window_hooks(None, None)
        control.set_messages_hook(None)
        control.set_restart_hook(None)
        quit_watch_stop.set()
        if tray is not None:
            try:
                tray.stop()
            except Exception as _e:
                logger.debug("ignorado (launcher): %s", type(_e).__name__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
