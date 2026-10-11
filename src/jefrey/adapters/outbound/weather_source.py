"""Clima atual de uma cidade (Open-Meteo, gratis e sem chave). So busca; o texto para a pessoa e montado em skills/essentials.py."""
from __future__ import annotations

from typing import Optional

import httpx


async def current_weather(city: str) -> Optional[tuple[dict, dict]]:
    """(lugar, tempo agora) ou None se a cidade nao existe. Levanta se o servico esta fora do ar."""
    async with httpx.AsyncClient(timeout=10) as c:
        g = await c.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": city, "count": 1, "language": "pt"})
        g.raise_for_status()
        results = g.json().get("results") or []
        if not results:
            return None
        r = results[0]
        w = await c.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": r["latitude"], "longitude": r["longitude"],
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,precipitation",
            "timezone": "auto"})
        w.raise_for_status()
        return r, (w.json().get("current") or {})


async def openrouter_key(code: str, verifier: str, url: str = "https://openrouter.ai/api/v1/auth/keys") -> str:
    """Troca o codigo do login do OpenRouter pela chave (PKCE). Devolve "" se nao veio chave."""
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(url, json={"code": code, "code_verifier": verifier, "code_challenge_method": "S256"})
        r.raise_for_status()
        return str(r.json().get("key") or "")
