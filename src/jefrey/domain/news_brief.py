"""Noticias direto, sem modelo (REGRAS PURAS): reconhece o pedido e monta a resposta com os titulos achados.

Rapido (so a busca) e sem invencao: so aparece o que a fonte disse. Titulos sao DADO de terceiros: viram texto, nunca instrucao.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional, Sequence

MAX_ITEMS = 3
MAX_TITLE = 110
MAX_TOPIC = 60

_ASK = re.compile(
    r"^(?:(?:me )?(?:da|passa|conta|mostra|traz|diz)\s+)?(?:(?:quais|qual|tem|ha)\s+(?:sao\s+)?)?(?:as\s+)?"
    r"(?:ultimas?\s+)?(?:noticias?|novidades?)(?:\s+(?:recentes?|de hoje|do dia))?(?:\s+(?:sobre|de|do|da|dos|das|em|com)\s+(?P<topic>.+))?$"
)
_TOPIC_NOISE = re.compile(r"\b(?:por favor|pra mim|agora|hoje)\b")


def _plain(text: str) -> str:
    s = unicodedata.normalize("NFD", text or "").encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s)).strip()


def _with_accents(topic: str, original: str) -> str:
    """A busca em portugues precisa dos acentos ('inteligência artificial'); sem eles ela devolve paginas em espanhol."""
    words = {}
    for w in re.findall(r"[\wÀ-ÿ]+", original or ""):
        words.setdefault(_plain(w), w.lower())
    return " ".join(words.get(tok, tok) for tok in topic.split())


def news_topic(message: str) -> Optional[str]:
    """Assunto pedido ('inteligencia artificial'), 'brasil' se pediu noticias sem assunto, ou None se nao e pedido de noticias."""
    msg = _plain(message)
    m = _ASK.match(msg)
    if not m:
        return None
    topic = _TOPIC_NOISE.sub(" ", m.group("topic") or "").strip()
    topic = re.sub(r"\s+", " ", topic)[:MAX_TOPIC]
    return _with_accents(topic, message) or "brasil"


def _clip(text: str) -> str:
    t = " ".join(str(text or "").split())
    return t if len(t) <= MAX_TITLE else t[: MAX_TITLE - 1].rstrip() + "…"


def compose(topic: str, results: Sequence[dict]) -> str:
    """Ate 3 manchetes com a fonte. Sem resultado, diz com clareza (nada inventado)."""
    items = []
    for r in results:
        title = _clip(r.get("title"))
        if not title:
            continue
        site = _clip(r.get("site") or "")
        items.append(f"- {title}" + (f" ({site})" if site else ""))
        if len(items) >= MAX_ITEMS:
            break
    if not items:
        return f"Não achei notícias recentes sobre {topic}."
    return f"Últimas notícias sobre {topic}:\n" + "\n".join(items)
