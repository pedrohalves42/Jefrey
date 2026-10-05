"""Skill: controlar o computador por voz (Windows): abrir programas, sites e pastas, e mudar o volume.

Seguranca: programas so pela lista do Menu Iniciar do proprio usuario (ou apelidos conhecidos); sites so http(s) e sem
credenciais na URL; pastas so as conhecidas do usuario. Nada digita, apaga, instala ou executa texto livre.
Controlar OUTROS programas por dentro (ex.: criar objetos no Blender) exige um conector proprio de cada programa e
nao esta aqui: o Jefrey diz isso com honestidade em vez de fingir.
"""
from __future__ import annotations

import logging
import os
import re
import sys
import time
import unicodedata
import webbrowser
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus, urlsplit

from src.jefrey.skills import SkillBase, SkillMetadata, skill, tool

logger = logging.getLogger(__name__)

ALIASES = {  # apelido falado -> programa do Windows
    "bloco de notas": "notepad.exe", "notepad": "notepad.exe", "calculadora": "calc.exe", "paint": "mspaint.exe",
    "explorador de arquivos": "explorer.exe", "explorador": "explorer.exe", "gerenciador de tarefas": "taskmgr.exe",
    "prompt de comando": "cmd.exe", "configuracoes": "ms-settings:", "relogio": "ms-clock:", "calendario": "outlookcal:",
}
SITES = {  # apelido falado -> endereco
    "youtube": "https://www.youtube.com", "gmail": "https://mail.google.com", "google": "https://www.google.com",
    "whatsapp": "https://web.whatsapp.com", "whatsapp web": "https://web.whatsapp.com", "agenda": "https://calendar.google.com",
    "google agenda": "https://calendar.google.com", "maps": "https://maps.google.com", "mapas": "https://maps.google.com",
    "drive": "https://drive.google.com", "wikipedia": "https://pt.wikipedia.org", "noticias": "https://g1.globo.com", "g1": "https://g1.globo.com",
}
FOLDERS = {  # apelido falado -> pasta do usuario
    "documentos": "Documents", "downloads": "Downloads", "baixados": "Downloads", "area de trabalho": "Desktop", "desktop": "Desktop",
    "imagens": "Pictures", "fotos": "Pictures", "musicas": "Music", "videos": "Videos",
}
_SKIP_APPS = re.compile(r"desinstal|uninstall|leia-?me|readme|manual|ajuda|help|licen[cç]a|license|suporte|support|site da|website", re.I)
MIN_MATCH = 0.72
_cache: dict = {"at": 0.0, "apps": {}}


def _norm(s: str) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", t).split())


# ---------------- apps ----------------
def start_menu_dirs() -> list[Path]:
    dirs = []
    for env in ("APPDATA", "PROGRAMDATA"):
        base = os.getenv(env)
        if base:
            dirs.append(Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return dirs


def scan_apps(force: bool = False) -> dict[str, Path]:
    """{nome normalizado: atalho .lnk} do Menu Iniciar (cache de 5 min)."""
    if not force and time.monotonic() - _cache["at"] < 300 and _cache["apps"]:
        return _cache["apps"]
    apps: dict[str, Path] = {}
    for d in start_menu_dirs():
        try:
            for p in d.rglob("*.lnk"):
                if _SKIP_APPS.search(p.stem):
                    continue
                apps.setdefault(_norm(p.stem), p)
        except OSError:
            continue
    _cache.update(at=time.monotonic(), apps=apps)
    return apps


def match_app(query: str, apps: dict[str, Path]) -> tuple[Optional[str], list[str]]:
    """(melhor nome, candidatos). Melhor = igual, ou contido, ou parecido; empate/duvida devolve so candidatos."""
    q = _norm(query)
    if not q:
        return None, []
    if q in apps:
        return q, [q]
    contained = [n for n in apps if q in n.split() or n.startswith(q) or (len(q) >= 4 and q in n)]
    if len(contained) == 1:
        return contained[0], contained
    scored = sorted(((SequenceMatcher(None, q, n).ratio(), n) for n in apps), reverse=True)
    good = [n for s, n in scored if s >= MIN_MATCH]
    if contained:
        return None, sorted(contained, key=len)[:4]
    if len(good) == 1 or (good and scored[0][0] - (scored[1][0] if len(scored) > 1 else 0) > 0.08):
        return good[0], good
    return None, good[:4]


def _start(target: str) -> None:
    os.startfile(target)  # type: ignore[attr-defined]  # so Windows


def _open_url(url: str) -> bool:
    return bool(webbrowser.open(url))


def _press(vk: int, times: int) -> None:
    import ctypes

    u = ctypes.windll.user32  # type: ignore[attr-defined]
    for _ in range(times):
        u.keybd_event(vk, 0, 0, 0)
        u.keybd_event(vk, 0, 2, 0)
        time.sleep(0.02)


MEDIA_KEYS = {"play": 0xB3, "pause": 0xB3, "tocar": 0xB3, "pausar": 0xB3, "continuar": 0xB3, "parar": 0xB2, "stop": 0xB2,
              "proxima": 0xB0, "proximo": 0xB0, "next": 0xB0, "pular": 0xB0, "anterior": 0xB1, "voltar": 0xB1, "previous": 0xB1}
PROTECTED = ("explorer", "jefrey", "system", "taskmgr", "csrss", "winlogon", "searchhost", "startmenuexperiencehost", "shellexperiencehost")


def list_windows() -> list[tuple[int, str, str]]:
    """Janelas visiveis com titulo: (identificador, titulo, nome do programa). So Windows."""
    import ctypes
    from ctypes import wintypes

    u, k = ctypes.windll.user32, ctypes.windll.kernel32  # type: ignore[attr-defined]
    out: list[tuple[int, str, str]] = []
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def each(hwnd, _):
        if not u.IsWindowVisible(hwnd):
            return True
        n = u.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(hwnd, buf, n + 1)
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        exe = ""
        h = k.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        if h:
            size = wintypes.DWORD(520)
            path = ctypes.create_unicode_buffer(520)
            if k.QueryFullProcessImageNameW(h, 0, path, ctypes.byref(size)):
                exe = Path(path.value).stem
            k.CloseHandle(h)
        out.append((int(hwnd), buf.value, exe))
        return True

    u.EnumWindows(proc(each), 0)
    return out


def _close_window(hwnd: int) -> None:
    import ctypes

    ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # type: ignore[attr-defined]  # WM_CLOSE: pede para fechar (o programa pergunta se quer salvar)


def match_windows(query: str, wins: list[tuple[int, str, str]]) -> list[tuple[int, str, str]]:
    """Janelas cujo programa ou titulo combina com o que a pessoa disse; nunca as protegidas."""
    q = _norm(query)
    if len(q) < 3:
        return []
    found = []
    for hwnd, title, exe in wins:
        if any(p in _norm(exe) for p in PROTECTED) or "jefrey" in _norm(title):
            continue
        if q in _norm(exe) or q in _norm(title):
            found.append((hwnd, title, exe))
    return found


def _windows_only() -> Optional[str]:
    return None if sys.platform == "win32" else "Isso só funciona no Windows."


def clean_url(text: str) -> Optional[str]:
    """Endereco seguro para abrir, ou None. So http(s), com ponto no nome e sem usuario/senha."""
    t = (text or "").strip().strip("\"'")
    if _norm(t) in SITES:
        return SITES[_norm(t)]
    if not re.match(r"^https?://", t, re.I):
        if re.match(r"^[\w.-]+\.[a-z]{2,}(/\S*)?$", t, re.I):
            t = "https://" + t
        else:
            return None
    p = urlsplit(t)
    if p.scheme not in ("http", "https") or not p.hostname or "." not in p.hostname or p.username or p.password or len(t) > 500:
        return None
    if p.hostname in ("localhost",) or re.match(r"^(127\.|10\.|192\.168\.|169\.254\.|0\.)", p.hostname) or p.hostname.endswith((".local", ".internal")):
        return None
    return t


class ComputerSkill(SkillBase):
    metadata = SkillMetadata(
        name="computer",
        description="Abrir programas, sites e pastas e mudar o volume do computador, por voz",
        tags=["utility", "local", "windows"],
        enabled_by_default=True,
    )

    def initialize(self) -> bool:
        return sys.platform == "win32"

    def get_tools(self) -> list:
        return [self.open_app, self.open_website, self.open_folder, self.set_volume, self.media_control, self.search_in_browser, self.close_app]

    @tool(description="Abre um programa do computador pelo nome (ex.: Word, Chrome, Bloco de Notas, Calculadora)")
    async def open_app(self, name: str, user_id: str | None = None) -> str:
        if (msg := _windows_only()):
            return msg
        key = _norm(name)
        if not key or len(key) > 60:
            return "Diga o nome do programa que você quer abrir."
        if key in ALIASES:
            try:
                _start(ALIASES[key])
            except OSError:
                return f"Não consegui abrir {name}."
            return f"Abri {name}."
        best, cands = match_app(name, scan_apps())
        if best is None:
            if cands:
                return "Encontrei mais de um: " + ", ".join(c.title() for c in cands) + ". Qual deles você quer?"
            return f"Não achei um programa chamado “{name}” neste computador."
        try:
            _start(str(scan_apps()[best]))
        except OSError:
            return f"Não consegui abrir {best.title()}."
        return f"Abri {best.title()}."

    @tool(description="Abre um site no navegador (ex.: YouTube, Gmail, g1.globo.com). So http(s)")
    async def open_website(self, site: str, user_id: str | None = None) -> str:
        url = clean_url(site)
        if url is None:
            return "Não consegui abrir esse endereço com segurança. Diga o nome do site, como YouTube, ou um endereço como g1.globo.com."
        ok = _open_url(url)
        return f"Abri {urlsplit(url).hostname} no navegador." if ok else "Não consegui abrir o navegador."

    @tool(description="Abre uma pasta do usuario: Documentos, Downloads, Area de Trabalho, Imagens, Musicas ou Videos")
    async def open_folder(self, name: str, user_id: str | None = None) -> str:
        if (msg := _windows_only()):
            return msg
        sub = FOLDERS.get(_norm(name))
        if sub is None:
            return "Eu abro Documentos, Downloads, Área de Trabalho, Imagens, Músicas e Vídeos. Qual deles?"
        path = Path.home() / sub
        if not path.is_dir():
            return f"A pasta {name} não existe neste computador."
        _start(str(path))
        return f"Abri a pasta {name}."

    @tool(description="Muda o volume do computador: acao 'aumentar', 'diminuir' ou 'mudo' (liga/desliga o som); passos de 1 a 10")
    async def set_volume(self, action: str, steps: int = 3, user_id: str | None = None) -> str:
        if (msg := _windows_only()):
            return msg
        a = _norm(action)
        n = max(1, min(10, int(steps or 3)))
        if a in ("aumentar", "subir", "mais", "up", "alto"):
            _press(0xAF, n)
            return "Aumentei o volume."
        if a in ("diminuir", "baixar", "menos", "down", "baixo"):
            _press(0xAE, n)
            return "Diminuí o volume."
        if a in ("mudo", "silenciar", "mute", "silencio", "tirar o som", "desmutar", "ligar o som"):
            _press(0xAD, 1)
            return "Mudei o som (mudo ligado ou desligado)."
        return "Diga se é para aumentar, diminuir ou deixar mudo."

    @tool(description="Controla a musica ou o video que estiver tocando: acao 'pausar', 'continuar', 'proxima', 'anterior' ou 'parar'")
    async def media_control(self, action: str, user_id: str | None = None) -> str:
        if (msg := _windows_only()):
            return msg
        vk = MEDIA_KEYS.get(_norm(action))
        if vk is None:
            return "Diga se é para pausar, continuar, passar para a próxima ou voltar."
        _press(vk, 1)
        return {0xB3: "Pausei ou continuei a reprodução.", 0xB0: "Passei para a próxima.", 0xB1: "Voltei para a anterior.", 0xB2: "Parei a reprodução."}[vk]

    @tool(description="Pesquisa um assunto no Google, abrindo o navegador com o resultado (ex.: 'receita de bolo')")
    async def search_in_browser(self, query: str, user_id: str | None = None) -> str:
        q = " ".join((query or "").split())[:200]
        if not q:
            return "O que você quer pesquisar?"
        ok = _open_url("https://www.google.com/search?q=" + quote_plus(q))
        return f"Pesquisei “{q}” no navegador." if ok else "Não consegui abrir o navegador."

    @tool(description="Fecha um programa aberto pelo nome (ex.: Word, Chrome). Pede para fechar com educacao: se houver algo sem salvar, o programa pergunta")
    async def close_app(self, name: str, user_id: str | None = None) -> str:
        if (msg := _windows_only()):
            return msg
        found = match_windows(name, list_windows())
        if not found:
            return f"Não vi nenhum programa aberto chamado “{name}”."
        exes = {e.lower() for _, _, e in found}
        if len(exes) > 1:
            return "Achei mais de um: " + ", ".join(sorted({e.title() or t for _, t, e in found})[:5]) + ". Qual deles você quer fechar?"
        for hwnd, _, _ in found:
            _close_window(hwnd)
        return f"Pedi para fechar {found[0][2].title() or name}. Se tiver algo sem salvar, ele vai perguntar."


@skill("computer", "Abrir programas, sites e pastas e mudar o volume do computador, por voz", tags=["utility", "local", "windows"])
class _ComputerSkillWrapper(ComputerSkill):
    pass
