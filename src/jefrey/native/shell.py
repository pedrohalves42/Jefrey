"""Janela propria do Jefrey (WebView2, o motor do Edge que ja vem no Windows 11): o programa abre como um app, sem navegador.

- o servidor continua o mesmo; a janela so mostra a tela dele (127.0.0.1);
- fechar a janela (X) esconde na bandeja: o Jefrey segue ouvindo, lembrando e avisando; "Sair" so pela bandeja;
- "orbe": uma bolinha pequena, sempre visivel, que abre a janela ao clicar;
- segunda abertura do programa so traz a janela existente para a frente (arquivo-sinal, sem rede);
- sem WebView2 (ou com JEFREY_WINDOW=browser) o launcher volta ao navegador, como antes.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

TITLE = "Jefrey"
MAIN_SIZE = (1180, 780)
MIN_SIZE = (860, 560)
ORB_SIZE = (276, 299)  # o Windows tira ~16 px de largura e ~39 de altura: o orbe fica com ~260 x 260
SIGNAL_FILE = "show.signal"
STATE_FILE = "window.json"
EXTERNAL_HOSTS = ("accounts.google.com", "console.cloud.google.com", "myaccount.google.com")

SPLASH = """<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Jefrey</title>
<style>html,body{height:100%;margin:0;background:#030a10;color:#cfeaf2;font-family:Segoe UI,system-ui,sans-serif}
body{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:22px}
.o{width:84px;height:84px;border-radius:50%;background:radial-gradient(circle at 35% 30%,#8ff3ff,#0aa5c2 55%,#04323f);
box-shadow:0 0 60px #06b6d466;animation:p 1.6s ease-in-out infinite}
@keyframes p{0%,100%{transform:scale(.92);opacity:.8}50%{transform:scale(1.08);opacity:1}}
h1{font-size:26px;font-weight:600;margin:0}p{margin:0;opacity:.65;font-size:16px}</style>
<div class="o"></div><h1>Jefrey</h1><p>@@MSG@@</p></html>"""


def splash(msg: str) -> str:
    return SPLASH.replace("@@MSG@@", msg)


def webview_available() -> bool:
    """Tem o pywebview e o WebView2 (motor do Edge)? Sem isso o launcher usa o navegador."""
    if sys.platform != "win32" or os.getenv("JEFREY_WINDOW", "").lower() == "browser":
        return False
    try:
        import webview  # noqa: F401
    except Exception as e:
        logger.info("janela propria indisponivel (%s)", type(e).__name__)
        return False
    return True


def is_external(url: str) -> bool:
    """Enderecos que abrem no navegador de verdade (o Google nao deixa entrar por dentro de janelas embutidas)."""
    from urllib.parse import urlsplit

    p = urlsplit(url or "")
    return p.scheme == "https" and (p.hostname or "") in EXTERNAL_HOSTS


def open_external(url: str) -> bool:
    if not is_external(url):
        return False
    return bool(webbrowser.open(url))


def signal_path(home: Path) -> Path:
    return home / "config" / SIGNAL_FILE


def ask_running_to_show(home: Path) -> None:
    """Segunda abertura: deixa um arquivo-sinal; a janela que ja esta aberta o ve e vem para a frente."""
    p = signal_path(home)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(time.time()), encoding="utf-8")
    except OSError as e:
        logger.info("nao consegui avisar a janela aberta (%s)", type(e).__name__)


QUIT_FILE = "quit.signal"


def quit_signal_path(home: Path) -> Path:
    return home / "config" / QUIT_FILE


def ask_running_to_quit(home: Path) -> None:
    """`Jefrey.exe --restart`: pede por arquivo-sinal (sem rede, sem senha) para a copia aberta fechar."""
    p = quit_signal_path(home)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(time.time()), encoding="utf-8")
    except OSError as e:
        logger.info("nao consegui pedir para fechar (%s)", type(e).__name__)


def clear_quit_signal(home: Path) -> None:
    try:
        quit_signal_path(home).unlink(missing_ok=True)
    except OSError as e:
        logger.debug("sinal de fechar: %s", type(e).__name__)


def watch_quit_signal(home: Path, on_quit: Callable[[], None], stop: threading.Event) -> threading.Thread:
    """Observa o arquivo-sinal de fechar (so de arquivos criados DEPOIS da abertura: lixo antigo e apagado no inicio)."""

    def loop() -> None:
        sig = quit_signal_path(home)
        while not stop.wait(1.0):
            try:
                if sig.exists():
                    sig.unlink(missing_ok=True)
                    on_quit()
                    return
            except OSError as e:
                logger.debug("sinal de fechar: %s", type(e).__name__)

    t = threading.Thread(target=loop, daemon=True, name="jefrey-quit-signal")
    t.start()
    return t


def restart_command(frozen: bool, executable: str) -> list[str]:
    """Comando que abre uma NOVA copia pedindo para a atual fechar antes. Programa instalado: Jefrey.exe --restart."""
    return [executable, "--restart"] if frozen else [executable, "-m", "src.jefrey.native", "--restart"]


def clamp_state(state: dict, screen: tuple[int, int]) -> dict:
    """Posicao/tamanho salvos so valem se a janela ficaria visivel (o monitor pode ter mudado)."""
    w = max(MIN_SIZE[0], min(int(state.get("w", MAIN_SIZE[0])), screen[0]))
    h = max(MIN_SIZE[1], min(int(state.get("h", MAIN_SIZE[1])), screen[1]))
    out: dict = {"w": w, "h": h, "fullscreen": bool(state.get("fullscreen", True))}  # tela cheia sem bordas e o padrao
    x, y = state.get("x"), state.get("y")
    if isinstance(x, int) and isinstance(y, int) and -50 <= x <= screen[0] - 120 and 0 <= y <= screen[1] - 120:
        out.update(x=x, y=y)
    return out


def load_state(home: Path) -> dict:
    try:
        d = json.loads((home / "config" / STATE_FILE).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(home: Path, state: dict) -> None:
    try:
        f = home / "config" / STATE_FILE
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        data = {k: state[k] for k in ("w", "h", "x", "y") if isinstance(state.get(k), int)}
        if isinstance(state.get("fullscreen"), bool):
            data["fullscreen"] = state["fullscreen"]
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, f)
    except OSError as e:
        logger.debug("estado da janela nao salvo (%s)", type(e).__name__)


class Api:
    """O que a tela pode pedir a janela (so isto, e so enderecos da lista)."""

    def __init__(self, shell: "DesktopShell"):
        self._shell = shell

    def open_external(self, url: str) -> bool:
        return open_external(str(url))

    def show_orb(self) -> bool:
        self._shell.show_orb()
        return True

    def expand(self) -> bool:
        self._shell.show()
        return True

    def toggle_fullscreen(self) -> bool:
        return self._shell.toggle_fullscreen()

    def is_fullscreen(self) -> bool:
        return self._shell.fullscreen

    def minimize(self) -> bool:
        self._shell.minimize()
        return True

    def hide_window(self) -> bool:
        self._shell.hide()
        return True

    def open_messages(self, user_id: str = "") -> bool:
        """Abre o WhatsApp dentro do Jefrey (a tela diz quem e a pessoa)."""
        return self._shell.show_messages(str(user_id or ""))


class DesktopShell:
    def __init__(self, url: str, home: Path, quit_cb: Callable[[], None], start_hidden: bool = False):
        self.url = url
        self.home = home
        self.quit_cb = quit_cb
        self.start_hidden = start_hidden
        self.main = None
        self.orb = None
        self.quitting = False
        self._hidden_notice = False
        self._state: dict = {}
        self._on_tray_notice: Optional[Callable[[str, str], None]] = None
        self._stop = threading.Event()
        self.fullscreen = True
        self.sites: dict = {}  # janelas das outras redes (Instagram, Facebook, X, Telegram)
        self._site_counts: dict = {}
        self.messages = None  # janela "Mensagens" (WhatsApp Web dentro do app), criada so quando preciso
        self._bridge = None

    # ---- mensagens (WhatsApp dentro do app) ----
    def _wa_bridge(self):
        if self._bridge is None:
            from src.jefrey.native.messages import WaBridge, pair_in_process

            self._bridge = WaBridge(self.url, self.home, pair_in_process)
        return self._bridge

    def _ensure_messages(self, hidden: bool) -> bool:
        """Cria a janela do WhatsApp Web (com o codigo da extensao rodando dentro). Segue viva escondida para o Jefrey continuar atento."""
        if self.messages is not None:
            return True
        try:
            import webview

            from src.jefrey.adapters.outbound.paths import extension_dir
            from src.jefrey.native.messages import TITLE as MSG_TITLE, WA_URL, WaApi, build_script

            ext = extension_dir()
            if ext is None:
                logger.warning("pasta da extensao nao encontrada: janela de mensagens indisponivel")
                return False
            script = build_script(ext)
            win = webview.create_window(
                MSG_TITLE, url=WA_URL, width=1180, height=800, min_size=(760, 520), background_color="#0b141a", js_api=WaApi(self._wa_bridge()),
                text_select=True, hidden=hidden,
            )

            def closing():
                if self.quitting:
                    return True
                try:
                    win.hide()
                except Exception as e:
                    logger.debug("hide mensagens: %s", type(e).__name__)
                return False

            def loaded():
                try:
                    win.evaluate_js(script)
                except Exception as e:
                    logger.info("nao consegui ligar o Jefrey no WhatsApp (%s)", type(e).__name__)

            win.events.closing += closing
            win.events.loaded += loaded
            self.messages = win
            return True
        except Exception as e:
            logger.warning("janela de mensagens indisponivel (%s)", type(e).__name__)
            return False

    # ---- outras redes: janela com login guardado, sem robo; o Jefrey so conta as novidades pelo titulo da pagina ----
    def _sites_file(self) -> Path:
        return self.home / "config" / "sites.json"

    def _remember_site(self, net_id: str) -> None:
        try:
            cur = json.loads(self._sites_file().read_text(encoding="utf-8"))
            cur = [x for x in cur if isinstance(x, str)]
        except (OSError, ValueError):
            cur = []
        if net_id not in cur:
            self._sites_file().parent.mkdir(parents=True, exist_ok=True)
            self._sites_file().write_text(json.dumps(cur + [net_id]), encoding="utf-8")

    def _ensure_site(self, net_id: str, hidden: bool) -> bool:
        from src.jefrey.domain.social import NETWORKS

        if net_id == "whatsapp" or net_id not in NETWORKS:
            return False
        if net_id in self.sites:
            return True
        try:
            import webview

            name, url = NETWORKS[net_id]
            win = webview.create_window(f"Jefrey · {name}", url=url, width=1180, height=800, min_size=(760, 520), background_color="#101418",
                                        text_select=True, hidden=hidden)

            def closing():
                if self.quitting:
                    return True
                try:
                    win.hide()
                except Exception as e:
                    logger.debug("hide %s: %s", net_id, type(e).__name__)
                return False

            win.events.closing += closing
            self.sites[net_id] = win
            self._remember_site(net_id)
            return True
        except Exception as e:
            logger.warning("janela de %s indisponivel (%s)", net_id, type(e).__name__)
            return False

    def show_site(self, net_id: str) -> bool:
        if not self._ensure_site(net_id, hidden=False):
            return False
        try:
            self.sites[net_id].show()
            self.sites[net_id].restore()
        except Exception as e:
            logger.info("nao consegui mostrar %s (%s)", net_id, type(e).__name__)
        return True

    def site_counts(self) -> dict:
        return dict(self._site_counts)

    def start_sites_hidden(self) -> None:
        """As redes que a pessoa ja abriu voltam escondidas (o login fica guardado), e o Jefrey segue contando as novidades."""
        try:
            for net in json.loads(self._sites_file().read_text(encoding="utf-8")):
                if isinstance(net, str):
                    self._ensure_site(net, hidden=True)
        except (OSError, ValueError):
            pass

        def poll() -> None:
            from src.jefrey.domain.social import unread_from_title

            while not self._stop.wait(30):
                for net, win in list(self.sites.items()):
                    try:
                        self._site_counts[net] = unread_from_title(str(win.evaluate_js("document.title") or ""))
                    except Exception as e:
                        logger.debug("titulo de %s: %s", net, type(e).__name__)

        threading.Thread(target=poll, daemon=True, name="jefrey-sites-poll").start()

    def show_messages(self, user_id: str = "") -> bool:
        bridge = self._wa_bridge()
        if user_id and not bridge.set_user(user_id):
            return False
        if not bridge.enabled():
            return False  # ainda nao sei quem e a pessoa: a tela do Jefrey precisa abrir primeiro
        if not self._ensure_messages(hidden=False):
            return False
        try:
            self.messages.show()
            self.messages.restore()
        except Exception as e:
            logger.info("nao consegui mostrar as mensagens (%s)", type(e).__name__)
        return True

    def start_messages_hidden(self) -> None:
        """Se a pessoa ja usou a janela de mensagens, ela volta escondida a cada abertura para o Jefrey seguir atento."""
        try:
            if self._wa_bridge().enabled():
                self._ensure_messages(hidden=True)
        except Exception as e:
            logger.info("mensagens nao iniciadas (%s)", type(e).__name__)

    # ---- acoes (podem ser chamadas de qualquer thread)
    def show(self) -> None:
        if self.main is None:
            return
        try:
            self._hide_orb()
            self.main.show()
            self.main.restore()
            from src.jefrey.native import hotkey

            hotkey.focus_window(TITLE)
        except Exception as e:
            logger.info("nao consegui mostrar a janela (%s)", type(e).__name__)

    def toggle_fullscreen(self) -> bool:
        """Tela cheia sem bordas <-> janela comum. Devolve se ficou em tela cheia. A escolha fica guardada."""
        if self.main is None:
            return self.fullscreen
        try:
            self.main.toggle_fullscreen()
            self.fullscreen = not self.fullscreen
            self._state["fullscreen"] = self.fullscreen
            save_state(self.home, self._state)
        except Exception as e:
            logger.info("tela cheia indisponivel (%s)", type(e).__name__)
        return self.fullscreen

    def minimize(self) -> None:
        try:
            if self.main is not None:
                self.main.minimize()
        except Exception as e:
            logger.debug("minimize: %s", type(e).__name__)

    def hide(self) -> None:
        try:
            if self.main is not None:
                self.main.hide()
        except Exception as e:
            logger.debug("hide: %s", type(e).__name__)

    def show_orb(self) -> None:
        if self.orb is None:
            return
        try:
            self.orb.show()
            self.hide()
        except Exception as e:
            logger.info("orbe indisponivel (%s)", type(e).__name__)

    def _hide_orb(self) -> None:
        try:
            if self.orb is not None:
                self.orb.hide()
        except Exception as e:
            logger.debug("orb hide: %s", type(e).__name__)

    def quit(self) -> None:
        if self.quitting:
            return
        self.quitting = True
        self._stop.set()
        self._snapshot()
        for w in (*self.sites.values(), self.messages, self.orb, self.main):
            try:
                if w is not None:
                    w.destroy()
            except Exception as e:
                logger.debug("destroy: %s", type(e).__name__)

    def set_tray_notice(self, fn: Callable[[str, str], None]) -> None:
        self._on_tray_notice = fn

    # ---- eventos da janela
    def _on_closing(self):
        """X da janela: esconde na bandeja, a nao ser que seja um pedido de sair."""
        if self.quitting:
            return True
        self._snapshot()
        self.hide()
        if not self._hidden_notice and self._on_tray_notice:
            self._hidden_notice = True
            self._on_tray_notice("Jefrey", "Continuo aqui, no relógio do Windows. Para fechar de vez: clique com o botão direito no ícone e escolha Sair.")
        return False

    def _snapshot(self) -> None:
        try:
            if self.main is not None:
                if not self.fullscreen:  # em tela cheia o tamanho e o da tela: nao vale guardar
                    self._state.update(w=int(self.main.width), h=int(self.main.height), x=int(self.main.x), y=int(self.main.y))
                self._state["fullscreen"] = self.fullscreen
                save_state(self.home, self._state)
        except Exception as e:
            logger.debug("snapshot: %s", type(e).__name__)

    # ---- inicio
    def _screen(self) -> tuple[int, int]:
        try:
            import webview

            s = webview.screens[0]
            return int(s.width), int(s.height)
        except Exception:
            return 1920, 1080

    def _watch_signal(self) -> None:
        sig = signal_path(self.home)
        while not self._stop.wait(0.6):
            try:
                if sig.exists():
                    sig.unlink(missing_ok=True)
                    self.show()
            except OSError as e:
                logger.debug("sinal: %s", type(e).__name__)

    def _allow_microphone(self) -> None:
        """O microfone e o proposito do app: libera so para a propria tela (127.0.0.1), sem a pergunta do Edge a cada abertura."""
        try:
            from Microsoft.Web.WebView2.Core import CoreWebView2PermissionKind as Kind, CoreWebView2PermissionState as State

            base = self.url

            def on_permission(_sender, args) -> None:
                if args.PermissionKind == Kind.Microphone and str(args.Uri).startswith(base):
                    args.State = State.Allow

            from System import Action

            def attach() -> None:
                self.main.native.webview.CoreWebView2.PermissionRequested += on_permission

            self.main.native.Invoke(Action(attach))  # o WebView2 so aceita ajuste na thread da janela
        except Exception as e:
            logger.warning("nao consegui liberar o microfone na janela (%s)", type(e).__name__)

    def run(self, wait_ready: Callable[[], bool]) -> None:
        """Abre a janela (thread principal) e bloqueia ate fechar de vez."""
        import webview

        api = Api(self)
        st = clamp_state(load_state(self.home), self._screen())
        self._state = dict(st)
        self.fullscreen = bool(st.get("fullscreen", True))
        self.main = webview.create_window(
            TITLE, html=splash("Acordando…"), width=st["w"], height=st["h"], x=st.get("x"), y=st.get("y"),
            min_size=MIN_SIZE, background_color="#030a10", js_api=api, text_select=True, hidden=self.start_hidden,
            fullscreen=self.fullscreen,
        )
        self.orb = webview.create_window(
            "Jefrey orbe", url=f"{self.url}/orb?app=1", width=ORB_SIZE[0], height=ORB_SIZE[1], frameless=True,
            easy_drag=True, on_top=True, resizable=False, hidden=True, min_size=(200, 200), background_color="#030a10", js_api=api, shadow=False,
        )
        self.main.events.closing += self._on_closing
        self.main.events.loaded += lambda: self._allow_microphone() if not getattr(self, '_mic_done', False) and not setattr(self, '_mic_done', True) else None

        def boot() -> None:
            ok = wait_ready()
            try:
                if ok:
                    self.main.load_url(f"{self.url}/?app=1")
                else:
                    self.main.load_html(splash("Não consegui iniciar. Abra o menu do relógio e escolha “Ver registros”."))
            except Exception as e:
                logger.warning("falha ao carregar a tela (%s)", type(e).__name__)
            self.start_messages_hidden()
            self.start_sites_hidden()
            self._watch_signal()

        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.settings["SHOW_DEFAULT_MENUS"] = False
        dbg = os.getenv("JEFREY_WEBVIEW_DEBUG_PORT", "")
        if dbg.isdigit():  # so para testes: permite inspecionar a janela por fora
            webview.settings["REMOTE_DEBUGGING_PORT"] = int(dbg)
        storage = self.home / "webview"
        storage.mkdir(parents=True, exist_ok=True)
        webview.start(boot, gui="edgechromium", private_mode=False, storage_path=str(storage))
        self._stop.set()
