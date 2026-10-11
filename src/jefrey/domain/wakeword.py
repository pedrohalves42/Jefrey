"""Palavra de ativacao: "Jefrey, que horas sao?".

A tela escuta segmentos de fala, o Whisper LOCAL transcreve e aqui decidimos se a fala COMECA chamando o Jefrey.
So a frase depois do nome e devolvida; o resto do que foi dito nunca sai desta funcao nem e guardado.
Para evitar disparo a toa (TV, conversa de outras pessoas), o nome precisa estar no INICIO da fala.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

NAMES = ("jefrey", "jeffrey", "jefri", "jefre", "jeferi", "jefrei", "geferi", "jefery", "jeffri", "jefrey's")
# Unicas chamadas aceitas ANTES do nome (frases exatas: "o Jefrey e legal" ou "e Jefrey chegou" nao chamam ninguem)
LEAD_PHRASES = {(), ("ei",), ("ola",), ("oi",), ("hey",), ("opa",), ("fala",), ("eai",), ("e", "ai"), ("oi", "ei"), ("ola", "ei"), ("ei", "ei")}
MIN_RATIO = 0.84
MAX_LEAD_WORDS = 2  # "ei jefrey", "e ai jefrey"


def _norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")


def _is_name(token: str) -> bool:
    t = re.sub(r"[^a-z']", "", _norm(token))
    if len(t) < 5 or len(t) > 9:
        return False
    return any(SequenceMatcher(None, t, n).ratio() >= MIN_RATIO for n in NAMES)


def find_wake(text: str) -> Optional[str]:
    """Se a fala comeca chamando o Jefrey, devolve o que veio depois ('' se so chamou); senao None."""
    words = (text or "").strip().split()
    for i in range(min(len(words), MAX_LEAD_WORDS + 1)):
        head = tuple(_norm(re.sub(r"[^\wÀ-ÿ']", "", w)) for w in words[:i])
        if head in LEAD_PHRASES and _is_name(words[i] if i < len(words) else ""):
            rest = " ".join(words[i + 1:]).lstrip(" ,.;:!?-—")
            return rest.strip()
    return None
