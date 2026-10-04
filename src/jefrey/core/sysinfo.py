"""Medidas simples do computador para os medidores do painel (so leitura, sem dependencias extras)."""
from __future__ import annotations

import sys
import time
from typing import Optional

_START = time.monotonic()
_last_cpu: Optional[tuple[int, int, int]] = None


def _filetime(ft) -> int:
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


def cpu_percent() -> Optional[float]:
    """Uso do processador (%) desde a ultima chamada. None se nao der para medir (nao Windows ou primeira chamada)."""
    global _last_cpu
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        idle, kern, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
        if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user)):  # type: ignore[attr-defined]
            return None
        cur = (_filetime(idle), _filetime(kern), _filetime(user))
    except Exception:
        return None
    prev, _last_cpu = _last_cpu, cur
    if prev is None:
        return None
    d_idle, d_kern, d_user = (cur[i] - prev[i] for i in range(3))
    total = d_kern + d_user  # o tempo de "kernel" ja inclui o ocioso
    return None if total <= 0 else round(max(0.0, min(100.0, (total - d_idle) * 100.0 / total)), 1)


def memory() -> tuple[float, float]:
    """(usada %, total em GB)."""
    from src.jefrey.core.hardware import read_memory_gb

    total, avail = read_memory_gb()
    if total <= 0:
        return 0.0, 0.0
    return round(max(0.0, min(100.0, (total - avail) * 100.0 / total)), 1), round(total, 1)


def uptime_s() -> int:
    return int(time.monotonic() - _START)


def snapshot() -> dict:
    used, total = memory()
    return {"ram_pct": used, "ram_total_gb": total, "cpu_pct": cpu_percent(), "uptime_s": uptime_s()}
