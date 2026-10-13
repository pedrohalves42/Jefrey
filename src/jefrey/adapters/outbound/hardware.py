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
    tools: str = "basico"  # "completo": usa todas as ferramentas | "basico": hora, contas, notas | "nenhum"

    @property
    def needs_gb(self) -> float:
        return round(self.size_gb * 1.4 + 0.5, 1)


# do mais capaz ao mais leve
# Medido em CPU comum (i7 8a geracao), 12 casos de ferramentas+conversa: ver docs/MODELOS.md
TIERS: tuple[ModelTier, ...] = (
    ModelTier("qwen2.5:14b", 9.0, "muito boa", "completo"),
    ModelTier("qwen2.5:7b", 4.7, "muito boa", "completo"),
    ModelTier("qwen2.5:3b", 1.9, "boa", "completo"),
    ModelTier("qwen3:1.7b", 1.4, "razoavel (padrao leve)", "basico"),
    ModelTier("qwen2.5:0.5b", 0.4, "basica (so para maquinas muito limitadas)", "nenhum"),
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


# ---------------------------------------------------------------- placa de video e sugestao de modelo local
@dataclass(frozen=True)
class GpuInfo:
    name: str
    vram_gb: float
    kind: str  # "nvidia" | "apple"


def _run_nvidia_smi() -> str:
    import subprocess

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                       capture_output=True, text=True, timeout=6, creationflags=flags)
    return r.stdout if r.returncode == 0 else ""


def detect_gpu(run_smi=_run_nvidia_smi, system: "str | None" = None, machine: "str | None" = None,
               total_ram_gb: "float | None" = None) -> "GpuInfo | None":
    """NVIDIA (via nvidia-smi) ou Apple Silicon (memoria unificada). Outras placas: desconhecido (None)."""
    import platform

    system = system or platform.system()
    machine = machine or platform.machine()
    if system == "Darwin" and machine == "arm64":
        total = total_ram_gb if total_ram_gb is not None else read_memory_gb()[0]
        return GpuInfo("Apple Silicon", round(total * 0.65, 1), "apple")  # parte da memoria unificada que a GPU usa
    try:
        out = run_smi()
    except (OSError, ValueError, Exception):  # nvidia-smi ausente ou travado
        return None
    best: "GpuInfo | None" = None
    for line in out.strip().splitlines():
        name, _, mem = line.rpartition(",")
        try:
            vram = float(mem.strip()) / 1024
        except ValueError:
            continue
        if best is None or vram > best.vram_gb:
            best = GpuInfo(name.strip() or "NVIDIA", round(vram, 1), "nvidia")
    return best


# limiares em GB de memoria de video, com folga; ESTIMATIVA (nao medida: sem GPU para testar)
GPU_TIERS: tuple[tuple[float, str, str], ...] = (
    (20.0, "gemma4:26b", "muito boa"),
    (11.0, "gemma4:e4b", "muito boa"),
    (8.0, "gemma4:e2b", "boa"),
)


def local_advice(gpu: "GpuInfo | None", ram_total_gb: float) -> dict:
    """Sugere modelo local SO quando ha placa de video capaz; senao recomenda a nuvem e explica por que."""
    if gpu is not None:
        for need, model, quality in GPU_TIERS:
            if gpu.vram_gb >= need:
                return {"suggest_local": True, "model": model, "quality": quality, "measured": False,
                        "reason": f"Seu computador tem {gpu.name} com cerca de {gpu.vram_gb:g} GB de memoria de video: "
                                  f"o modelo {model} deve rodar bem (estimativa).",
                        "gpu": {"name": gpu.name, "vram_gb": gpu.vram_gb, "kind": gpu.kind}}
        why = f"A placa ({gpu.name}, {gpu.vram_gb:g} GB) e pequena para os modelos locais bons."
    else:
        why = ("Nao encontrei uma placa de video compativel. Em teste com processador comum (sem placa), "
               "modelos locais bons levaram de 35 segundos a mais de 2 minutos por resposta.")
    return {"suggest_local": False, "model": None, "quality": None, "measured": False,
            "reason": why + " Recomendamos usar a nuvem.", "gpu": None if gpu is None else
            {"name": gpu.name, "vram_gb": gpu.vram_gb, "kind": gpu.kind}}
