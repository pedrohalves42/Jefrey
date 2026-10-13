"""O Windows de verdade: Menu Iniciar, abrir programas e sites, teclas de midia, listar e fechar janelas. As regras ficam em domain/computer.py."""
from __future__ import annotations

import os
import time
import webbrowser
from pathlib import Path

from src.jefrey.domain.computer import _SKIP_APPS, _norm

_cache: dict = {"at": 0.0, "apps": {}}


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
