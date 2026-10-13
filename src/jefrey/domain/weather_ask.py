"""Perguntas simples de clima ("como esta o clima em Curitiba?", "vai chover hoje?") para responder direto, sem rodadas do modelo. Regra pura."""
from __future__ import annotations

import re
import unicodedata
from typing import Optional


def _plain(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")


_WHERE = r"(?:\s+(?:em|para|pra|no|na)\s+(?P<city>[a-z .'-]{2,60}?))?"
_WHEN = r"(?:\s+(?:agora|hoje|neste momento|atual))?"
_PATTERNS = [
    re.compile(rf"^(?:(?:como\s+esta|qual\s+(?:e\s+)?(?:a|o)|me\s+diga\s+(?:a|o))\s+)?(?:o\s+|a\s+)?(?:clima|tempo|temperatura|previsao do tempo){_WHEN}{_WHERE}{_WHEN}$"),
    re.compile(rf"^(?:vai|va)\s+chover{_WHEN}(?:\s+amanha)?{_WHERE}{_WHEN}$"),
    re.compile(rf"^(?:esta|ta)\s+(?:frio|calor|chovendo){_WHEN}{_WHERE}{_WHEN}$"),
    re.compile(rf"^(?:que\s+)?(?:graus|temperatura)\s+(?:esta|faz|tem){_WHEN}{_WHERE}{_WHEN}$"),
]


def weather_ask(original: str) -> Optional[str]:
    """None se a mensagem NAO e so uma pergunta de clima; "" se e, sem cidade (usar a da pessoa); senao o nome da cidade."""
    orig = (original or "").strip().rstrip("?!. ")
    msg = _plain(orig)
    if not msg or len(msg) > 90:
        return None
    for pat in _PATTERNS:
        m = pat.match(msg)
        if m:
            city = (m.group("city") or "").strip() if "city" in pat.groupindex else ""
            if city and len(orig) == len(msg):  # mantem os acentos que a pessoa escreveu ("Piçarras")
                city = orig[m.start("city"):m.end("city")].strip()
            return city
    return None
