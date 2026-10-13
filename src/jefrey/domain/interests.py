"""Assuntos de noticia que combinam com o que o Jefrey aprendeu da pessoa. Regra pura: texto entra, ids de assunto saem."""
from __future__ import annotations

import re
import unicodedata

KEYWORDS: dict[str, tuple[str, ...]] = {
    "tecnologia": ("tecnologia", "computador", "programacao", "programar", "internet", "celular", "inteligencia artificial", "software", "gadget", "python", "robo", "informatica"),
    "ciencia": ("ciencia", "saude", "medicina", "espaco", "astronomia", "pesquisa", "remedio", "vacina", "nutricao"),
    "politica": ("politica", "governo", "eleicao", "eleicoes", "presidente", "congresso"),
    "mundo": ("guerra", "internacional", "exterior", "diplomacia"),
    "economia": ("investimento", "investir", "bolsa", "economia", "acoes", "dolar", "financas", "mercado", "poupanca"),
    "esportes": ("futebol", "esporte", "corrida", "academia", "basquete", "tenis", "volei", "treino", "campeonato", "time"),
    "cultura": ("filme", "serie", "musica", "cinema", "livro", "teatro", "show", "novela", "famosos", "cantor"),
    "carros": ("carro", "moto", "automovel", "motor", "oficina"),
    "educacao": ("estudo", "faculdade", "curso", "escola", "aprender", "universidade", "concurso"),
    "natureza": ("natureza", "planta", "orquidea", "jardim", "animal", "pesca", "bicho", "horta", "cachorro", "gato"),
    "viagem": ("viagem", "viajar", "turismo", "praia", "ferias", "hotel", "passeio"),
}
MAX_SUGGESTED = 6


def _plain(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")


def suggest(texts: list[str], exclude: list[str] | None = None) -> list[str]:
    """Assuntos mais citados nos textos (do que mais para o que menos), sem os que a pessoa ja escolheu."""
    blob = " ".join(_plain(t) for t in texts)
    skip = set(exclude or [])
    scored: list[tuple[int, str]] = []
    for topic, words in KEYWORDS.items():
        if topic in skip:
            continue
        hits = sum(len(re.findall(rf"\b{re.escape(w)}", blob)) for w in words)
        if hits:
            scored.append((hits, topic))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [t for _, t in scored][:MAX_SUGGESTED]
