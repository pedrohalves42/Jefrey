"""Oferta da area de transferencia: guarda UMA oferta pendente (em memoria) e se a pessoa ligou o recurso (em arquivo).

O recurso fica DESLIGADO ate a pessoa ligar. Nada e colado de volta: a oferta so vira um pedido de texto ao Jefrey quando ela escolher.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Optional

from src.jefrey.domain.clipboard import prompt_for


class OfferStore:
    def __init__(self, path: Path):
        self._path = Path(path)
        self._offer: Optional[dict] = None
        self._lock = threading.Lock()

    def enabled(self) -> bool:
        try:
            return bool(json.loads(self._path.read_text(encoding="utf-8")).get("enabled", False))
        except (OSError, ValueError):
            return False

    def set_enabled(self, value: bool) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps({"enabled": bool(value)}), encoding="utf-8")
        if not value:
            self.dismiss()

    def set(self, offer: dict) -> None:
        with self._lock:
            self._offer = {"text": str(offer.get("text", "")), "offers": list(offer.get("offers", []))}

    def get(self) -> Optional[dict]:
        with self._lock:
            return dict(self._offer) if self._offer else None

    def dismiss(self) -> None:
        with self._lock:
            self._offer = None

    def prompt(self, action: str) -> str:
        offer = self.get()
        if offer is None:
            raise ValueError("sem texto copiado")
        if action not in offer["offers"]:
            raise ValueError("acao desconhecida")
        return prompt_for(action, offer["text"])


_SHARED: Optional[OfferStore] = None


def shared_store() -> OfferStore:
    """Uma loja so para o programa inteiro (o observador grava, a API le)."""
    global _SHARED
    if _SHARED is None:
        _SHARED = OfferStore(Path(os.getenv("JEFREY_CONFIG_DIR", "config")) / "clipboard.json")
    return _SHARED
