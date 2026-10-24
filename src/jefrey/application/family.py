"""Modo familia: guarda o consentimento (ligado + contato) e avisa uma vez por semana que o resumo esta pronto para enviar."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from src.jefrey.domain.family import offer_due


class FamilyStore:
    def __init__(self, path: Path):
        self._path = Path(path)

    def _load(self) -> dict:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def get(self, user_id: str) -> dict:
        d = self._load().get(user_id, {})
        return {"enabled": bool(d.get("enabled")), "contact": str(d.get("contact", "")), "last_offer": d.get("last_offer")}

    def set_consent(self, user_id: str, enabled: bool, contact: str) -> dict:
        data = self._load()
        cur = data.get(user_id, {})
        data[user_id] = {**cur, "enabled": bool(enabled) and bool((contact or "").strip()), "contact": (contact or "").strip()[:80]}
        self._save(data)
        return self.get(user_id)

    def mark_offered(self, user_id: str, day_iso: str) -> None:
        data = self._load()
        data.setdefault(user_id, {})["last_offer"] = day_iso
        self._save(data)


class FamilyOffer:
    def __init__(self, store: FamilyStore, users: Callable[[], list[str]], notify: Callable[[str, str, str], bool], now: Callable[[], datetime]):
        self._store, self._users, self._notify, self._now = store, users, notify, now

    async def tick(self) -> list[str]:
        now, sent = self._now(), []
        for uid in self._users():
            c = self._store.get(uid)
            if offer_due(now, c["last_offer"], c["enabled"], c["contact"]):
                if self._notify(uid, "Resumo da semana", f"Quer enviar o resumo da semana para {c['contact']}? Diga: enviar resumo para a família."):
                    self._store.mark_offered(uid, now.date().isoformat())
                    sent.append(uid)
        return sent


_SHARED: Optional[FamilyStore] = None


def shared_store() -> FamilyStore:
    global _SHARED
    if _SHARED is None:
        _SHARED = FamilyStore(Path(os.getenv("JEFREY_CONFIG_DIR", "config")) / "family.json")
    return _SHARED
