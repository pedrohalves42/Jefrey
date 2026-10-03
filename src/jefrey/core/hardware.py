"""Recomendacao de modelo local conforme a memoria disponivel (funciona em qualquer hardware).

Tamanhos sao do modelo quantizado (Q4) no Ollama. Reservamos folga para contexto e
para o resto do sistema: precisa = tamanho * 1.4 + 0.5 GB.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelTier:
    model: str
    size_gb: float
    quality: str  # descricao curta para o usuario

    @property
    def needs_gb(self) -> float:
        return round(self.size_gb * 1.4 + 0.5, 1)


# do mais capaz ao mais leve
TIERS: tuple[ModelTier, ...] = (
    ModelTier("qwen2.5:14b", 9.0, "muito boa"),
    ModelTier("qwen2.5:7b", 4.7, "muito boa"),
    ModelTier("qwen2.5:3b", 1.9, "boa"),
    ModelTier("qwen2.5:1.5b", 1.0, "razoavel (padrao)"),
    ModelTier("qwen2.5:0.5b", 0.4, "basica (so para maquinas muito limitadas)"),
)


def recommend_model(available_gb: float) -> ModelTier:
    """Maior modelo que cabe na memoria disponivel; nunca abaixo do menor."""
    for t in TIERS:
        if available_gb >= t.needs_gb:
            return t
    return TIERS[-1]


def read_memory_gb() -> tuple[float, float]:
    """(total, disponivel) em GB. Linux/container via /proc, Windows via ctypes."""
    try:
        info = {}
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                k, _, v = line.partition(":")
                info[k] = int(v.strip().split()[0])
        return info["MemTotal"] / 1048576, info.get("MemAvailable", info["MemFree"]) / 1048576
    except (OSError, KeyError, ValueError):
        pass
    if os.name == "nt":
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                        ("avail", ctypes.c_ulonglong), ("pt", ctypes.c_ulonglong),
                        ("pa", ctypes.c_ulonglong), ("vt", ctypes.c_ulonglong), ("va", ctypes.c_ulonglong),
                        ("ex", ctypes.c_ulonglong)]
        ms = MS()
        ms.l = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
        return ms.total / 2**30, ms.avail / 2**30
    return 0.0, 0.0
