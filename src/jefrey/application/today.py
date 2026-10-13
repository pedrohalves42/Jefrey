"""Casos de uso do painel "Hoje": agenda, lembretes, clima, noticias, mercado e a sua regiao, num lugar so.

Regras:
- fontes publicas e gratuitas, SEM chave e sem mandar nada seu: so o nome da cidade vai ao servico de clima;
- cada cartao falha sozinho (um fora do ar nunca derruba o painel) e tem estado: ok | parcial | erro | falta_regiao;
- titulos de noticias sao DADO de terceiros: viram so texto na tela, nunca vao ao modelo nem acionam ferramentas;
- links so https; feeds com DOCTYPE/ENTITY ou enormes sao descartados;
- resposta em cache por 15 minutos.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable

from src.jefrey.domain.today import FEEDS, G1, INTERESTS, mix_interest_news

logger = logging.getLogger(__name__)


async def _section(name: str, coro, *, empty_ok: bool = False) -> dict:
    try:
        data = await coro
    except LookupError:
        return {"status": "desconectado", "items": []}
    except Exception as e:
        logger.info("painel do dia: %s falhou (%s)", name, type(e).__name__)
        return {"status": "erro", "items": []}
    if isinstance(data, list):
        return {"status": "ok" if (data or empty_ok) else "vazio", "items": data}
    return {"status": "ok", **data}


async def build(*, user_id: str, sources: Any, prefs: dict, agenda: Callable[[str], Awaitable[list]], reminders: Callable[[str], Awaitable[list]]) -> dict:
    """Monta o painel. `sources` traz feed/market/weather; `agenda` e `reminders` sao do usuario; cada cartao falha sozinho."""
    has_region = bool(prefs["uf"] and prefs["city"])

    async def market():
        m = await sources.market()
        if not m:
            raise RuntimeError("sem dados")  # (vazio nao foi para o cache: a proxima abertura tenta de novo)
        return {"status_override": "ok" if len(m) >= 3 else "parcial", **m}

    async def region():
        return await sources.feed(f"{G1}{prefs['uf']}/")

    async def weather():
        return await sources.weather(prefs["city"])

    async def foryou():
        topics = prefs["interests"]
        lists = await asyncio.gather(*[sources.feed(INTERESTS[t][1]) for t in topics], return_exceptions=True)
        got = {t: l[:4] for t, l in zip(topics, lists) if isinstance(l, list)}
        items = mix_interest_news(got)
        if not items:
            raise RuntimeError("sem noticias")
        return items

    secs = ["news", "economy", "market", "agenda", "reminders"] + (["region", "weather"] if has_region else [])
    jobs = [_section("news", sources.feed(FEEDS["news"])), _section("economy", sources.feed(FEEDS["economy"])), _section("market", market()),
            _section("agenda", agenda(user_id), empty_ok=True), _section("reminders", reminders(user_id), empty_ok=True)]
    if has_region:
        jobs += [_section("region", region()), _section("weather", weather())]
    if prefs["interests"]:
        secs.append("foryou")
        jobs.append(_section("foryou", foryou()))
    res = dict(zip(secs, await asyncio.gather(*jobs)))
    if "foryou" not in res:
        res["foryou"] = {"status": "sem_interesses", "items": []}
    if "market" in res and res["market"].get("status_override"):
        res["market"]["status"] = res["market"].pop("status_override")
    if not has_region:
        res["region"] = {"status": "falta_regiao", "items": []}
        res["weather"] = {"status": "falta_regiao"}
    return {"generated_at": datetime.now().isoformat(timespec="minutes"), "region": prefs, "sections": res}
