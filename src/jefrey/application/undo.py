"""Desfazer o que o Jefrey fez: diario por pessoa, das ultimas 24 horas, com a acao inversa de cada tipo.

Cada acao reversivel (criar lembrete, criar nota, gravar arquivo) deixa uma entrada com o que e preciso para voltar atras.
O que nao tem volta (enviar mensagem, publicar) fica registrado como "irreversible" e e dito com clareza.
`undoers` (tipo -> funcao que desfaz) e injetado: este modulo nao conhece banco nem arquivos.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

WINDOW = timedelta(hours=24)
MAX_ENTRIES = 200


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UndoJournal:
    def __init__(self, path: Path):
        self._path = Path(path)
        self._lock = threading.Lock()

    def _load(self) -> list[dict]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _save(self, items: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(items[-MAX_ENTRIES:], ensure_ascii=False), encoding="utf-8")

    def record(self, user_id: str, label: str, kind: str, payload: dict, now: Optional[datetime] = None) -> None:
        with self._lock:
            items = self._load()
            items.append({"user": user_id, "label": label[:120], "kind": kind, "payload": payload, "at": (now or _now()).isoformat()})
            self._save(items)

    def last(self, user_id: str, now: Optional[datetime] = None) -> Optional[dict]:
        limite = (now or _now()) - WINDOW
        for e in reversed(self._load()):
            if e.get("user") == user_id and datetime.fromisoformat(e["at"]) >= limite:
                return e
        return None

    def undo_last(self, user_id: str, undoers: dict[str, Callable[[dict], None]], now: Optional[datetime] = None) -> str:
        with self._lock:
            entry = self.last(user_id, now)
            if entry is None:
                return "Não tem nada para desfazer."
            items = self._load()
            if entry["kind"] == "irreversible" or entry["kind"] not in undoers:
                items.remove(entry)
                self._save(items)
                return f"Isso não dá para desfazer: {entry['label']}."
            try:
                undoers[entry["kind"]](entry["payload"])
            except Exception:
                return f"Não consegui desfazer agora: {entry['label']}. Tente de novo daqui a pouco."
            items.remove(entry)
            self._save(items)
            return f"Pronto, desfiz: {entry['label']}."


_SHARED: Optional[UndoJournal] = None


def shared_journal() -> UndoJournal:
    """Um diario so para o programa inteiro (as ferramentas gravam, a ferramenta "desfazer" le)."""
    global _SHARED
    if _SHARED is None:
        _SHARED = UndoJournal(Path(os.getenv("JEFREY_CONFIG_DIR", "config")) / "undo.json")
    return _SHARED
