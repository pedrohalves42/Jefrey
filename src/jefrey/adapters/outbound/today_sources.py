"""Fontes do painel "Hoje": agenda, lembretes, clima, noticias, mercado e a sua regiao, num lugar so.

Regras:
- fontes publicas e gratuitas, SEM chave e sem mandar nada seu: so o nome da cidade vai ao servico de clima;
- cada cartao falha sozinho (um fora do ar nunca derruba o painel) e tem estado: ok | parcial | erro | falta_regiao;
- titulos de noticias sao DADO de terceiros: viram so texto na tela, nunca vao ao modelo nem acionam ferramentas;
- links so https; feeds com DOCTYPE/ENTITY ou enormes sao descartados;
- resposta em cache por 15 minutos.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from src.jefrey.domain.today import (
    FEEDS, G1, INTERESTS, TTL, _clean, clean_interests, normalize_prefs, parse_rss, validate_region, weather_summary,
)

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[float, Any]] = {}


def _prefs_file() -> Path:
    return Path(os.getenv("JEFREY_CONFIG_DIR", "config")) / "today.json"


def load_prefs() -> dict:
    try:
        return normalize_prefs(json.loads(_prefs_file().read_text(encoding="utf-8")))
    except (OSError, ValueError, AttributeError):
        return {"city": "", "uf": "", "interests": []}


def _write_prefs(city: str, uf: str, interests: list[str]) -> None:
    f = _prefs_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"city": city, "uf": uf, "interests": interests}, ensure_ascii=False), encoding="utf-8")
    _cache.clear()


def save_prefs(city: str, uf: str) -> None:
    city, uf = validate_region(city, uf)
    _write_prefs(city, uf, load_prefs()["interests"])


def save_interests(ids: list[str]) -> list[str]:
    """Guarda os assuntos escolhidos (so os conhecidos, sem repetir, no maximo MAX_INTERESTS)."""
    clean = clean_interests(ids)
    cur = load_prefs()
    _write_prefs(cur["city"], cur["uf"], clean)
    return clean


async def _feed(c: httpx.AsyncClient, url: str) -> list[dict]:
    r = await c.get(url, headers={"User-Agent": "Mozilla/5.0 Jefrey"})
    if r.status_code != 200:
        raise RuntimeError(f"feed {r.status_code}")
    return parse_rss(r.content)


# ---------------- mercado ----------------
async def fetch_market(*, transport: Optional[httpx.AsyncBaseTransport] = None) -> dict:
    out: dict = {}
    async with httpx.AsyncClient(timeout=10, transport=transport, follow_redirects=False) as c:
        async def moedas():
            r = await c.get("https://economia.awesomeapi.com.br/json/last/USD-BRL,EUR-BRL,BTC-BRL")
            r.raise_for_status()
            d = r.json()
            for key, name in (("USDBRL", "usd"), ("EURBRL", "eur"), ("BTCBRL", "btc")):
                if key in d:
                    out[name] = {"value": float(d[key]["bid"]), "pct": float(d[key]["pctChange"])}

        async def ibov():
            r = await c.get("https://query1.finance.yahoo.com/v8/finance/chart/%5EBVSP", params={"range": "1d", "interval": "1d"}, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            m = r.json()["chart"]["result"][0]["meta"]
            v, prev = float(m["regularMarketPrice"]), float(m["chartPreviousClose"])
            out["ibov"] = {"value": v, "pct": (v - prev) * 100 / prev if prev else 0.0}

        for attempt in (1, 2):
            jobs = [moedas()] if "usd" not in out else []
            jobs += [ibov()] if "ibov" not in out else []
            for job in await asyncio.gather(*jobs, return_exceptions=True):
                if isinstance(job, Exception):
                    logger.info("painel do dia: fonte de mercado falhou na tentativa %s (%s)", attempt, type(job).__name__)
            if "usd" in out and "ibov" in out:
                break
            await asyncio.sleep(0.5 if transport is not None else 2.0)
    return out


# ---------------- clima ----------------
async def fetch_weather(city: str, *, transport: Optional[httpx.AsyncBaseTransport] = None) -> dict:
    async with httpx.AsyncClient(timeout=10, transport=transport, follow_redirects=False) as c:
        g = await c.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": city, "count": 1, "language": "pt", "countryCode": "BR"})
        g.raise_for_status()
        res = (g.json().get("results") or [None])[0]
        if not res:
            raise RuntimeError("cidade nao encontrada")
        w = await c.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": res["latitude"], "longitude": res["longitude"], "timezone": "auto", "forecast_days": 1,
            "current": "temperature_2m,weather_code", "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max"})
        w.raise_for_status()
        return weather_summary(res, w.json())


# ---------------- dados do usuario (locais) ----------------
async def _agenda(user_id: str) -> list[dict]:
    from src.jefrey.core import google_oauth as G

    if not G.status(user_id).get("connected"):
        raise LookupError("google nao conectado")
    from src.jefrey.adapters.outbound.system_adapters import calendar_events

    now = datetime.now(timezone.utc)
    end = now.replace(hour=23, minute=59, second=59)
    evs = await calendar_events(user_id, now, end, 6)
    return [{"title": _clean(e.get("summary", "Compromisso"), 80), "time": str(e.get("start") or "")[11:16] if "T" in str(e.get("start") or "") else ""} for e in evs]


async def _reminders(user_id: str) -> list[dict]:
    from src.jefrey.core.reminders import ReminderStore

    return [{"text": r["text"], "due_label": r["due_label"]} for r in ReminderStore().pending(user_id)[:6]]



def _cached(key: str):
    hit = _cache.get(key)
    return hit[1] if hit and time.monotonic() - hit[0] < TTL else None


async def _cached_call(key: str, make):
    v = _cached(key)
    if v is not None:
        return v
    v = await make()
    if v:  # resultado vazio nunca fica em cache: uma falha de rede passageira nao pode "grudar" por 15 minutos
        _cache[key] = (time.monotonic(), v)
    return v


class HttpPanelSources:
    """As fontes publicas do painel (RSS, mercado, clima) com cache de 15 minutos."""

    def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.transport = transport

    async def feed(self, url: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=10, transport=self.transport, follow_redirects=False) as c:
            return await _cached_call("feed:" + url, lambda: _feed(c, url))

    async def market(self) -> dict:
        return await _cached_call("market", lambda: fetch_market(transport=self.transport))

    async def weather(self, city: str) -> dict:
        return await _cached_call("weather:" + city, lambda: fetch_weather(city, transport=self.transport))
