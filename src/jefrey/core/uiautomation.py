"""Automacao segura de janelas (Windows): focar uma janela, digitar texto e usar poucos atalhos.

Regras que nao mudam:
- so age na janela CONFIRMADA (`expect_hwnd`): se o foco mudou, nao digita;
- nunca age em janelas protegidas (Explorer, Gerenciador de Tarefas, o proprio Jefrey...);
- texto e so texto (SendInput Unicode): nada vai para shell, nada e interpretado;
- atalhos so da lista fechada ALLOWED_HOTKEYS.
O chamador (a ferramenta do agente) ainda precisa da aprovacao da pessoa: aqui e a ultima barreira, nao a unica.
"""
from __future__ import annotations

import re
import sys
import time
from typing import Optional

MAX_TEXT = 500

VK = {"ctrl": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B, "tab": 0x09, "enter": 0x0D, "esc": 0x1B,
      "a": 0x41, "c": 0x43, "f": 0x46, "s": 0x53, "v": 0x56, "x": 0x58, "y": 0x59, "z": 0x5A, "d": 0x44}
ALLOWED_HOTKEYS = {"ctrl+c", "ctrl+v", "ctrl+x", "ctrl+a", "ctrl+s", "ctrl+z", "ctrl+y", "ctrl+f", "alt+tab", "enter", "esc", "tab", "win+d"}


class UIError(Exception):
    """Mensagem em portugues simples, pronta para a tela."""


def _protected(win: tuple[int, str, str]) -> bool:
    from src.jefrey.skills.computer import PROTECTED, _norm

    _, title, exe = win
    return any(p in _norm(exe) for p in PROTECTED) or "jefrey" in _norm(title)


class _WinBackend:
    """Backend real (ctypes). Nos testes e trocado por um falso."""

    def foreground(self) -> tuple[int, str, str]:
        import ctypes

        from src.jefrey.skills.computer import list_windows

        fg = int(ctypes.windll.user32.GetForegroundWindow())  # type: ignore[attr-defined]
        return next((w for w in list_windows() if w[0] == fg), (fg, "", ""))

    def windows(self) -> list[tuple[int, str, str]]:
        from src.jefrey.skills.computer import list_windows

        return list_windows()

    def set_foreground(self, hwnd: int) -> bool:
        import ctypes

        u = ctypes.windll.user32  # type: ignore[attr-defined]
        if u.IsIconic(hwnd):
            u.ShowWindow(hwnd, 9)  # SW_RESTORE
        u.keybd_event(0x12, 0, 0, 0)  # um toque no Alt libera a troca de foco (regra do Windows)
        u.keybd_event(0x12, 0, 2, 0)
        u.SetForegroundWindow(hwnd)
        time.sleep(0.15)
        return int(u.GetForegroundWindow()) == hwnd

    def _send(self, items: list[tuple[int, int, int]]) -> None:
        """items: (virtual-key, unicode, flags). SendInput em lote."""
        import ctypes
        from ctypes import wintypes

        ulong_ptr = ctypes.c_size_t

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ulong_ptr)]

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ulong_ptr)]

        class _U(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

        class INPUT(ctypes.Structure):
            _fields_ = [("type", wintypes.DWORD), ("u", _U)]

        arr = (INPUT * len(items))()
        for i, (vk, uni, flags) in enumerate(items):
            arr[i].type = 1  # INPUT_KEYBOARD
            arr[i].u.ki = KEYBDINPUT(vk, uni, flags, 0, 0)
        sent = ctypes.windll.user32.SendInput(len(items), arr, ctypes.sizeof(INPUT))  # type: ignore[attr-defined]
        if sent != len(items):
            raise UIError("O Windows não deixou eu digitar nessa janela.")

    def send_text(self, text: str) -> None:
        for ch in text:
            code = ord(ch)
            units = [code] if code < 0x10000 else [0xD800 + ((code - 0x10000) >> 10), 0xDC00 + ((code - 0x10000) & 0x3FF)]
            batch = []
            for u in units:
                batch += [(0, u, 0x0004), (0, u, 0x0004 | 0x0002)]  # KEYEVENTF_UNICODE, depois soltar
            self._send(batch)
            time.sleep(0.004)

    def send_keys(self, vks: list[int]) -> None:
        self._send([(v, 0, 0) for v in vks] + [(v, 0, 0x0002) for v in reversed(vks)])


_B: object = _WinBackend()


def _need_windows() -> None:
    if sys.platform != "win32" and isinstance(_B, _WinBackend):
        raise UIError("Isso só funciona no Windows.")


def foreground() -> tuple[int, str, str]:
    _need_windows()
    return _B.foreground()  # type: ignore[attr-defined]


def focus(name: str) -> int:
    """Traz a janela pedida para a frente e devolve o seu identificador. Nunca janelas protegidas."""
    _need_windows()
    from src.jefrey.skills.computer import match_windows

    found = match_windows(name, _B.windows())  # type: ignore[attr-defined]
    if not found:
        raise UIError(f"Não vi nenhum programa aberto chamado “{name}”.")
    if len({w[2].lower() for w in found}) > 1:
        raise UIError("Achei mais de um: " + ", ".join(sorted({(w[2] or w[1]).title() for w in found})[:5]) + ". Qual deles?")
    hwnd = found[0][0]
    if not _B.set_foreground(hwnd):  # type: ignore[attr-defined]
        raise UIError("Não consegui trazer essa janela para a frente.")
    return hwnd


def _confirmed(expect_hwnd: int) -> None:
    fg = foreground()
    if fg[0] != expect_hwnd:
        raise UIError("A janela mudou antes de eu agir. Não fiz nada; tente de novo.")
    if _protected(fg):
        raise UIError("Essa janela é protegida: não posso digitar nela.")


def clean_text(text: str) -> str:
    t = (text or "").replace("\t", " ")
    return "".join(c for c in t if c == "\n" or c >= " ").strip("\r")


def type_text(text: str, *, expect_hwnd: int) -> None:
    t = clean_text(text)
    if not t.strip():
        raise UIError("Diga o que eu devo digitar.")
    if len(t) > MAX_TEXT:
        raise UIError(f"O texto é grande demais para digitar (até {MAX_TEXT} letras).")
    _confirmed(expect_hwnd)
    _B.send_text(t)  # type: ignore[attr-defined]


def hotkey(combo: str, *, expect_hwnd: int) -> None:
    key = re.sub(r"\s+", "", (combo or "").lower())
    if key not in ALLOWED_HOTKEYS:
        raise UIError("Esse atalho não está na lista que eu posso usar: " + ", ".join(sorted(ALLOWED_HOTKEYS)) + ".")
    _confirmed(expect_hwnd)
    _B.send_keys([VK[p] for p in key.split("+")])  # type: ignore[attr-defined]


def last_window_title(hwnd: int) -> Optional[str]:
    return next((w[1] for w in _B.windows() if w[0] == hwnd), None)  # type: ignore[attr-defined]
