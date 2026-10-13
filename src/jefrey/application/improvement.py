"""Melhoria com a sua aprovacao: um 👎 vira um caso de teste local (pergunta, resposta ruim e o que seria esperado, vazio).

O programa NUNCA altera o proprio codigo: so grava um arquivo novo na pasta de casos. Quem decide o que mudar e a pessoa.
Texto com cara de senha ou chave nao e guardado.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.jefrey.domain.learning import has_secret

MAX_QUESTION = 500
MAX_ANSWER = 2000


def _safe_name(message_id: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_-]+", "-", message_id or "").strip("-")[:60] or "caso"
    return base


def save_case(dest: Path, message_id: str, question: str, answer: str, note: str = "") -> Optional[Path]:
    """Grava um caso em `dest`. Devolve o arquivo, ou None se o texto tiver segredo."""
    if has_secret(question) or has_secret(answer) or has_secret(note):
        return None
    dest.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    arq = dest / f"{stamp}-{_safe_name(message_id)}.json"
    caso = {
        "message_id": (message_id or "")[:120], "question": (question or "")[:MAX_QUESTION], "answer": (answer or "")[:MAX_ANSWER],
        "expected": "", "note": (note or "")[:300], "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    arq.write_text(json.dumps(caso, ensure_ascii=False, indent=2), encoding="utf-8")
    return arq
