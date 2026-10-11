"""Perguntas simples sobre e-mail novo ("tenho e-mail novo?", "quantos nao lidos?") respondidas direto. Regra pura."""
from __future__ import annotations

import json
import re
import unicodedata

_PATTERNS = [
    re.compile(r"^(?:eu\s+)?tenho\s+(?:algum\s+|algum\s+)?e-?mails?\s+(?:novos?|nao\s+lidos?)$"),
    re.compile(r"^(?:eu\s+)?tenho\s+(?:algum\s+)?(?:novo\s+)?e-?mail$"),
    re.compile(r"^quantos\s+e-?mails?\s+(?:nao\s+lidos?|novos?)(?:\s+(?:eu\s+)?tenho)?$"),
    re.compile(r"^(?:quais\s+(?:sao\s+)?)?(?:os\s+)?(?:meus\s+)?e-?mails?\s+(?:novos?|nao\s+lidos?)$"),
    re.compile(r"^(?:ve|veja|ver|mostra|mostre)\s+(?:os\s+)?(?:meus\s+)?e-?mails?\s+(?:novos?|nao\s+lidos?)$"),
    re.compile(r"^(?:chegou|chegaram)\s+(?:algum\s+)?e-?mails?(?:\s+novos?)?$"),
]
QUERY = "is:unread in:inbox"


def _plain(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")


def asks_unread_email(original: str) -> bool:
    msg = _plain((original or "").strip().rstrip("?!. "))
    return bool(msg) and len(msg) <= 70 and any(p.match(msg) for p in _PATTERNS)


def _sender(raw: str) -> str:
    name = re.sub(r"<[^>]*>", "", raw or "").strip(' "\'')
    return " ".join((name or raw or "alguém").split())[:40]


def format_unread(content: str) -> str:
    """Texto para a pessoa a partir do resultado da busca (JSON). Nunca levanta erro."""
    try:
        items = json.loads(content)
    except (ValueError, TypeError):
        return "Não consegui ler seus e-mails agora. Tente de novo daqui a pouco."
    if not isinstance(items, list):
        return "Não consegui ler seus e-mails agora. Tente de novo daqui a pouco."
    if items and isinstance(items[0], dict) and "error" in items[0]:
        return "Não consegui ler seus e-mails agora. Em Conexões → Google, veja se o Google continua conectado."
    total = next((i["total_estimado"] for i in items if isinstance(i, dict) and "total_estimado" in i), None)
    msgs = [i for i in items if isinstance(i, dict) and "subject" in i]
    if not msgs:
        return "Você não tem e-mails novos na caixa de entrada. Tudo em dia!"
    n = total if isinstance(total, int) else len(msgs)
    head = f"Você tem {'cerca de ' if isinstance(total, int) and total > len(msgs) else ''}{n} e-mail{'s' if n != 1 else ''} não lido{'s' if n != 1 else ''}."
    lines = [f"- {_sender(m.get('from', ''))}: {' '.join(str(m.get('subject', '')).split())[:70]}" for m in msgs[:5]]
    return head + "\nOs mais recentes:\n" + "\n".join(lines)
