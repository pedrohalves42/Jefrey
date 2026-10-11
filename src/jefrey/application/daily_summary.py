"""Caso de uso: resumo do dia a partir do painel "Hoje" (agenda, lembretes, clima), sem chamar modelo de IA.

`panel_loader(user_id)` devolve o painel (o mesmo de GET /today, com cache); injetado para o teste nao depender da rede.
Cada fonte que nao respondeu vira "nao consegui ver"; as outras seguem.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

from src.jefrey.domain.daily_summary import compose

_USABLE = ("ok", "vazio")


def _items(sections: dict, name: str) -> Optional[list]:
    sec = sections.get(name) or {}
    return list(sec.get("items") or []) if sec.get("status") in _USABLE else None


async def light_panel(user_id: str, *, agenda: Callable[[str], Awaitable[list]], reminders: Callable[[str], Awaitable[list]],
                      weather: Callable[[str], Awaitable[dict]], city: str) -> dict:
    """So o que o resumo precisa (agenda, lembretes e clima): sem noticias, bolsa e cambio, que atrasam. Cada fonte falha sozinha."""
    import asyncio

    from src.jefrey.application.today import _section

    nomes = ["agenda", "reminders"]
    jobs = [_section("agenda", agenda(user_id), empty_ok=True), _section("reminders", reminders(user_id), empty_ok=True)]
    if city:
        nomes.append("weather")
        jobs.append(_section("weather", weather(city)))
    return {"sections": dict(zip(nomes, await asyncio.gather(*jobs)))}


async def build_daily_summary(*, user_id: str, name: Optional[str], now: datetime,
                              panel_loader: Callable[[str], Awaitable[dict]]) -> str:
    try:
        panel: Any = await panel_loader(user_id)
        sections = (panel or {}).get("sections") or {}
    except Exception:
        sections = {}
    weather = sections.get("weather") or {}
    return compose(
        name=name, now=now,
        agenda=_items(sections, "agenda"), reminders=_items(sections, "reminders"),
        weather=weather if weather.get("status") == "ok" else None,
    )
