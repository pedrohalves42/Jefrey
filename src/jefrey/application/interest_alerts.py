"""Alerta diario dos assuntos de interesse: um aviso por dia, em horario de gente acordada, com uma novidade de cada assunto.

Titulos de noticias sao DADO de terceiros: viram so texto do aviso, nunca vao ao modelo nem acionam ferramentas.
Uma fonte fora do ar nao bloqueia as outras; se todas falharem, o dia NAO e marcado como feito (tenta de novo mais tarde).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, Mapping, Optional

logger = logging.getLogger(__name__)

START_HOUR, END_HOUR = 8, 21  # avisa entre 8h e 21h59
MAX_TOPICS = 3
MAX_TITLE = 90


class InterestAlerts:
    def __init__(self, *, interests: Callable[[str], list[str]], headlines: Callable[[str], Awaitable[list[dict]]],
                 notify: Callable[[str, str, str], bool], users: Callable[[], list[str]], now: Callable[[], datetime],
                 labels: Mapping[str, str], state_path: Path):
        self._interests, self._headlines, self._notify = interests, headlines, notify
        self._users, self._now, self._labels, self._path = users, now, labels, Path(state_path)

    def _load(self) -> dict:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, state: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(state), encoding="utf-8")

    async def tick(self) -> list[str]:
        """Roda de tempos em tempos. Devolve as pessoas avisadas agora."""
        now = self._now()
        if not (START_HOUR <= now.hour <= END_HOUR):
            return []
        today = now.date().isoformat()
        state = self._load()
        sent: list[str] = []
        for uid in self._users():
            if state.get(uid) == today:
                continue
            topics = [t for t in self._interests(uid) if t in self._labels][:MAX_TOPICS]
            if not topics:
                continue
            parts: list[str] = []
            for t in topics:
                try:
                    items = await self._headlines(t)
                except Exception as e:
                    logger.info("alerta de assunto %s: fonte indisponivel (%s)", t, type(e).__name__)
                    continue
                if items:
                    title = " ".join(str(items[0].get("title", "")).split())[:MAX_TITLE]
                    if title:
                        parts.append(f"{self._labels[t]}: {title}")
            if not parts:
                continue  # nada para dizer agora: nao marca o dia, tenta de novo mais tarde
            if self._notify(uid, "Novidades dos seus assuntos", " · ".join(parts)):
                state[uid] = today
                sent.append(uid)
        if sent:
            self._save(state)
        return sent
