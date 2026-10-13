"""Recordacao inteligente: decide QUANDO vale buscar na memoria e QUAIS lembrancas mostrar ("Lembrei de...").

Buscar memoria em toda mensagem custa tempo (e dinheiro, com embeddings na nuvem). Saudacao, hora, lembrete e
conversa solta nao precisam. So buscamos quando a pessoa fala de si, do passado ou pergunta algo que pode depender dela.
"""
from __future__ import annotations

import re
import unicodedata

_PAST = re.compile(r"\b(ontem|anteontem|semana passada|mes passado|outro dia|na ultima vez|ultima vez|antes|conversamos|falamos|te contei|te falei|lembra|lembrou|lembro|esqueci)\b")
_SELF = re.compile(r"\b(meu|minha|meus|minhas|eu|me|comigo|sobre mim|do meu|da minha|nosso|nossa)\b")
_ASK = re.compile(r"\b(qual|quais|quando|onde|quem|como|quanto|o que|que dia|por que|porque|sabe|recomenda|sugere|indica|devo|posso)\b")
_SKIP = re.compile(r"^(oi|ola|bom dia|boa tarde|boa noite|tudo bem|e ai|obrigad[oa]|valeu|ok|certo|beleza|tchau|ate mais|sim|nao|pode ser)\b[\s!.,?]*$")
_EXACT = re.compile(r"\b(que horas|que hora|horas sao|que dia e hoje|data de hoje|me lembra|me lembre|lembrete|guarda|anota|anote|quais sao meus lembretes|minhas notas)\b")

_STOP = {"que", "qual", "quais", "como", "onde", "quando", "quem", "para", "pra", "com", "uma", "uns", "umas", "isso", "esse", "essa", "esta",
         "este", "voce", "voces", "sobre", "mais", "muito", "meu", "minha", "meus", "minhas", "ainda", "tambem", "porque", "fazer", "pode",
         "tenho", "estou", "sabe", "algo", "coisa", "quero", "preciso", "gostaria", "hoje", "agora", "depois", "antes", "ontem", "seu", "sua"}


def mentions_past(text: str) -> bool:
    """A pessoa fala do passado ("ontem", "lembra"): vale buscar no diario."""
    return bool(_PAST.search(_norm(text)))


def _norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")


def needs_recall(text: str) -> bool:
    """Vale buscar nas memorias para responder isto?"""
    t = " ".join(_norm(text).split())
    if len(t) < 8 or _SKIP.match(t) or _EXACT.search(t):
        return False
    if _PAST.search(t):
        return True
    if _SELF.search(t) and (_ASK.search(t) or "?" in text):
        return True
    return bool(_ASK.search(t) and len(t) >= 25 and "?" in text)


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{4,}", _norm(s)) if w not in _STOP}


def relevant_facts(question: str, facts: list[str], limit: int = 3) -> list[str]:
    """Fatos guardados que tem a ver com a pergunta (sobreposicao de palavras; 5 letras iniciais tratam plural/flexao)."""
    q = {w[:5] for w in _words(question)}
    scored = []
    for f in facts:
        overlap = len(q & {w[:5] for w in _words(f)})
        if overlap:
            scored.append((overlap, f))
    scored.sort(key=lambda x: -x[0])
    return [f for _, f in scored[:limit]]


def asks_about_me(text: str) -> bool:
    t = _norm(text)
    return bool(re.search(r"\b(o que (voce )?sabe sobre mim|o que (voce )?aprendeu sobre mim|quem sou eu|o que voce lembra de mim|me conhece)\b", t))


def chips(question: str, fact_texts: list[str], memories: list[dict], diary_lines: list[str] | None = None,
          study_lines: list[str] | None = None) -> list[dict]:
    """Itens para "Lembrei de...": curtos, sem repetir, no maximo 4."""
    items: list[dict] = []
    seen: set[str] = set()

    def add(kind: str, text: str) -> None:
        text = " ".join(str(text).split())[:140]
        key = _norm(text)
        if text and key not in seen and len(items) < 5:
            seen.add(key)
            items.append({"kind": kind, "text": text})

    shown = fact_texts[:3] if asks_about_me(question) else relevant_facts(question, fact_texts)
    for f in shown:
        add("fato", f)
    for m in memories[:2]:
        add("lembranca", m.get("content", "") if isinstance(m, dict) else str(m))
    for d in diary_lines or []:
        add("diario", d)
    for s in study_lines or []:
        add("estudo", s.replace("Guia estudado: ", "Estudei sobre ", 1))
    return items
