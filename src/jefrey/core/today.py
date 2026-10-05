"""Painel "Hoje": agenda, lembretes, clima, noticias, mercado e a sua regiao, num lugar so.

Regras:
- fontes publicas e gratuitas, SEM chave e sem mandar nada seu: so o nome da cidade vai ao servico de clima;
- cada cartao falha sozinho (um fora do ar nunca derruba o painel) e tem estado: ok | parcial | erro | falta_regiao;
- titulos de noticias sao DADO de terceiros: viram so texto na tela, nunca vao ao modelo nem acionam ferramentas;
- links so https; feeds com DOCTYPE/ENTITY ou enormes sao descartados;
- resposta em cache por 15 minutos.
"""
from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger(__name__)

TTL = 15 * 60
MAX_FEED = 2_000_000  # o feed real do g1 tem ~420 KB
UFS = {"ac", "al", "ap", "am", "ba", "ce", "df", "es", "go", "ma", "mt", "ms", "mg", "pa", "pb", "pr", "pe", "pi", "rj", "rn", "rs", "ro", "rr", "sc", "sp", "se", "to"}
G1 = "https://g1.globo.com/rss/g1/"
FEEDS = {"news": G1, "economy": G1 + "economia/"}
_cache: dict[str, tuple[float, Any]] = {}
_TAG = re.compile(r"<[^>]+>")
_WEATHER_CODES = {0: "céu limpo", 1: "poucas nuvens", 2: "parcialmente nublado", 3: "nublado", 45: "neblina", 48: "neblina", 51: "garoa", 53: "garoa", 55: "garoa forte",
                  61: "chuva fraca", 63: "chuva", 65: "chuva forte", 71: "neve", 80: "pancadas de chuva", 81: "pancadas de chuva", 82: "chuva muito forte", 95: "trovoadas", 96: "trovoadas com granizo", 99: "trovoadas com granizo"}


# ---------------- preferencias (so a regiao) ----------------
def _prefs_file() -> Path:
    return Path(os.getenv("JEFREY_CONFIG_DIR", "config")) / "today.json"


def load_prefs() -> dict:
    try:
        d = json.loads(_prefs_file().read_text(encoding="utf-8"))
        return {"city": str(d.get("city", ""))[:60], "uf": str(d.get("uf", "")).lower() if str(d.get("uf", "")).lower() in UFS else ""}
    except (OSError, ValueError, AttributeError):
        return {"city": "", "uf": ""}


def save_prefs(city: str, uf: str) -> None:
    city, uf = " ".join((city or "").split()), (uf or "").strip().lower()
    if uf not in UFS:
        raise ValueError("Escolha o seu estado.")
    if not re.fullmatch(r"[A-Za-zÀ-ÿ' .-]{2,60}", city):
        raise ValueError("Escreva o nome da sua cidade (só letras, até 60).")
    f = _prefs_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"city": city, "uf": uf}, ensure_ascii=False), encoding="utf-8")
    _cache.clear()


# ---------------- noticias ----------------
def _clean(s: str, n: int = 180) -> str:
    return " ".join(html.unescape(_TAG.sub("", s or "")).split())[:n]


def parse_rss(content: bytes, limit: int = 6) -> list[dict]:
    """Titulos e links (https) de um RSS. Qualquer coisa estranha vira lista vazia."""
    if not content or len(content) > MAX_FEED or b"<!DOCTYPE" in content[:2000].upper() or b"<!ENTITY" in content.upper():
        return []
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []
    out = []
    for item in root.iter("item"):
        title = _clean(item.findtext("title") or "")
        link = (item.findtext("link") or "").strip()
        p = urlsplit(link)
        if title and p.scheme == "https" and p.hostname and not p.username:
            out.append({"title": title, "link": link})
        if len(out) >= limit:
            break
    return out


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
        d = w.json()
    cur, day = d.get("current") or {}, d.get("daily") or {}
    first = lambda k: (day.get(k) or [None])[0]
    desc = _WEATHER_CODES.get(int(cur.get("weather_code", 0) or 0), "tempo variável")
    rain = first("precipitation_probability_max")
    summary = f"Agora {round(cur.get('temperature_2m', 0))} °C, {desc}. Hoje entre {round(first('temperature_2m_min'))} e {round(first('temperature_2m_max'))} °C"
    summary += f", chance de chuva de {rain}%." if rain is not None else "."
    return {"place": ", ".join(x for x in (res.get("name"), res.get("admin1")) if x), "temp": cur.get("temperature_2m"), "max": first("temperature_2m_max"),
            "min": first("temperature_2m_min"), "rain_pct": rain, "summary": summary}


# ---------------- dados do usuario (locais) ----------------
async def _agenda(user_id: str) -> list[dict]:
    from src.jefrey.core import google_oauth as G

    if not G.status(user_id).get("connected"):
        raise LookupError("google nao conectado")
    from src.jefrey.skills.calendar import CalendarSkill

    now = datetime.now(timezone.utc)
    end = now.replace(hour=23, minute=59, second=59)
    evs = await CalendarSkill().list_events(time_min=now.isoformat(), time_max=end.isoformat(), max_results=6, user_id=user_id)
    return [{"title": _clean(e.get("summary", "Compromisso"), 80), "time": str((e.get("start") or {}).get("dateTime", ""))[11:16]} for e in (evs or [])]


async def _reminders(user_id: str) -> list[dict]:
    from src.jefrey.core.reminders import ReminderStore

    return [{"text": r["text"], "due_label": r["due_label"]} for r in ReminderStore().pending(user_id)[:6]]


# ---------------- painel ----------------
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


async def build(*, user_id: str, transport: Optional[httpx.AsyncBaseTransport] = None) -> dict:
    prefs = load_prefs()
    has_region = bool(prefs["uf"] and prefs["city"])

    async def feed(url):
        async with httpx.AsyncClient(timeout=10, transport=transport, follow_redirects=False) as c:
            return await _cached_call("feed:" + url, lambda: _feed(c, url))

    async def market():
        m = await _cached_call("market", lambda: fetch_market(transport=transport))
        if not m:
            raise RuntimeError("sem dados")  # (vazio nao foi para o cache: a proxima abertura tenta de novo)
        return {"status_override": "ok" if len(m) >= 3 else "parcial", **m}

    async def region():
        return await feed(f"{G1}{prefs['uf']}/")

    async def weather():
        return await _cached_call("weather:" + prefs["city"], lambda: fetch_weather(prefs["city"], transport=transport))

    secs = ["news", "economy", "market", "agenda", "reminders"] + (["region", "weather"] if has_region else [])
    jobs = [_section("news", feed(FEEDS["news"])), _section("economy", feed(FEEDS["economy"])), _section("market", market()),
            _section("agenda", _agenda(user_id), empty_ok=True), _section("reminders", _reminders(user_id), empty_ok=True)]
    if has_region:
        jobs += [_section("region", region()), _section("weather", weather())]
    res = dict(zip(secs, await asyncio.gather(*jobs)))
    if "market" in res and res["market"].get("status_override"):
        res["market"]["status"] = res["market"].pop("status_override")
    if not has_region:
        res["region"] = {"status": "falta_regiao", "items": []}
        res["weather"] = {"status": "falta_regiao"}
    return {"generated_at": datetime.now().isoformat(timespec="minutes"), "region": prefs, "sections": res}
