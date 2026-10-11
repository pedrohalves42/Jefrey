"""Observador da area de transferencia do Windows: so TEXTO, so quando a pessoa ligou, nunca guarda nem envia nada sozinho.

`read_text`, `sequence` e `on_offer` sao injetados (teste sem Windows). Desligado, nem le o conteudo.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from src.jefrey.domain.clipboard import offers_for

logger = logging.getLogger(__name__)


class ClipboardWatcher:
    def __init__(self, read_text: Callable[[], str], sequence: Callable[[], int], on_offer: Callable[[dict], None], enabled: Callable[[], bool]):
        self._read, self._seq, self._on_offer, self._enabled = read_text, sequence, on_offer, enabled
        self._last = self._seq()

    def poll(self) -> None:
        seq = self._seq()
        if seq == self._last:
            return
        self._last = seq
        if not self._enabled():
            return
        text = self._read()
        offers = offers_for(text)
        if offers:
            self._on_offer({"text": text, "offers": offers, "at": time.time()})

    def start(self, interval: float = 1.0) -> threading.Thread:
        def loop() -> None:
            while True:
                try:
                    self.poll()
                except Exception:
                    logger.debug("observador da area de transferencia falhou", exc_info=True)
                time.sleep(interval)

        t = threading.Thread(target=loop, name="clipboard-watch", daemon=True)
        t.start()
        return t


def win_sequence() -> int:
    import ctypes

    return int(ctypes.windll.user32.GetClipboardSequenceNumber())


def win_read_text() -> str:
    """Le o texto (Unicode) da area de transferencia. Qualquer falha devolve vazio."""
    import ctypes

    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.GetClipboardData.restype = ctypes.c_void_p
    kernel32.GlobalLock.restype = ctypes.c_void_p
    if not user32.OpenClipboard(None):
        return ""
    try:
        handle = user32.GetClipboardData(13)  # CF_UNICODETEXT
        if not handle:
            return ""
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()
